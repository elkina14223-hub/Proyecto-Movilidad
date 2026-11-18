"""API REST del MVP de movilidad de la Avenida Pradilla (Chía) - KAN-40."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anyio.from_thread
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from .entorno import estado_entorno
from . import ipv as ipvlib
from . import mensajeria, migrate, models, seed
from .database import Base, SessionLocal, engine, get_db

BOGOTA = timezone(timedelta(hours=-5))  # Colombia no usa horario de verano
VIGENCIA_REPORTE_MIN = 60
SAL = os.getenv("REPORT_SALT", "cambiar-en-produccion")
MAX_REPORTES_POR_HORA = 5

_hits: dict[str, deque] = defaultdict(deque)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Postgres: extensión PostGIS primero, luego tablas, luego el resto de migraciones
    Base.metadata.create_all(bind=engine)
    migrate.aplicar(engine)
    with SessionLocal() as db:
        if os.getenv("SEED_DEMO_DATA", "1") == "1":
            seed.seed(db)
    yield


app = FastAPI(
    title="Movilidad Av. Pradilla (Chía)",
    description="Horas pico, Índice de Presión Vial (IPV), rutas alternativas y planificador de salida.",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8080").split(",") if o],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Detrás de Render (o de cualquier proxy) el HTTPS se detecta por X-Forwarded-Proto
    if request.headers.get("x-forwarded-proto", request.url.scheme) == "https":
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi")):
        host = request.headers.get("host", "")
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: https://api.maptiler.com https://tile.openstreetmap.org; "
            f"style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' wss://{host} https://api.maptiler.com https://tile.openstreetmap.org; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        resp.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
    resp.headers["Cache-Control"] = "no-store" if request.method != "GET" else resp.headers.get("Cache-Control", "public, max-age=60")
    if "server" in resp.headers:
        del resp.headers["server"]
    return resp


def _dia_hora_actual() -> tuple[int, int]:
    ahora = datetime.now(BOGOTA)
    return ahora.weekday(), ahora.hour


def _dia(dia: int = Query(..., ge=0, le=6, description="0 = lunes ... 6 = domingo")) -> int:
    return dia


# ----------------------------------------------------------------- utilidades
@app.get("/api/health", tags=["sistema"])
def health(db: Session = Depends(get_db)):
    n = db.query(models.RegistroTrafico).count()
    return {"estado": "ok", "registros_trafico": n}


@app.get("/api/entorno", tags=["sistema"])
def entorno(request: Request, db: Session = Depends(get_db)):
    """Estado de publicación: servidor, hosting, dominio y certificado (sin datos sensibles)."""
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    resp = estado_entorno(
        host_cabecera=request.headers.get("host", ""),
        esquema=request.headers.get("x-forwarded-proto", request.url.scheme),
        protocolo_tls=request.headers.get("x-tls-protocol"),
        cifrado=request.headers.get("x-tls-cipher"),
        db_ok=db_ok,
    )
    resp["mensajeria"] = mensajeria.estado()
    return resp


@app.get("/api/fuentes", tags=["transparencia"])
def fuentes(db: Session = Depends(get_db)):
    """RNF-OTR: fuente y periodo de los datos, y explicación del IPV."""
    filas = db.query(models.RegistroTrafico.fuente, models.RegistroTrafico.periodo).distinct().all()
    return {
        "fuentes": [{"fuente": f, "periodo": p} for f, p in filas],
        "es_demostracion": any("sint" in f.lower() for f, _ in filas),
        "ipv_explicacion": (
            "El Índice de Presión Vial (IPV) va de 0 a 100 y resume qué tan cargada suele estar "
            "la avenida en un tramo, día y hora. 0-33 fluido, 34-66 moderado, 67-100 congestionado. "
            "Se calcula con el histórico de mediciones y se ajusta temporalmente con reportes de la "
            "comunidad que hayan sido confirmados por otras personas y sigan vigentes."
        ),
        "privacidad": "No pedimos registro. No guardamos tu IP ni tu ubicación. Ley 1581 de 2012.",
    }


# ----------------------------------------------------------------- RF-01 a RF-03
@app.get("/api/tramos", tags=["tráfico"])
def listar_tramos(db: Session = Depends(get_db)):
    return [{
        "codigo": t.codigo, "nombre": t.nombre, "longitud_m": t.longitud_m,
        "geometria": json.loads(t.geometria),
    } for t in db.query(models.Tramo).order_by(models.Tramo.codigo)]


@app.get("/api/trafico/horas", tags=["tráfico"])
def trafico_por_hora(dia: int = Query(..., ge=0, le=6), db: Session = Depends(get_db)):
    """RF-01: IPV por hora del día con las horas pico marcadas."""
    reportes = ipvlib.reportes_vigentes_validados(db)
    ahora_dia, _ = _dia_hora_actual()
    aplicar = dia == ahora_dia
    horas = []
    for h in range(24):
        v = ipvlib.ipv_promedio(db, dia, h, reportes, aplicar_reportes=aplicar)
        horas.append({"hora": h, "ipv": round(v), **ipvlib.clasificar(v)})
    umbral = 67
    for x in horas:
        x["pico"] = x["ipv"] >= umbral
    picos = [x["hora"] for x in horas if x["pico"]]
    return {"dia_semana": dia, "dia": ipvlib.DIAS[dia], "horas": horas, "horas_pico": picos}


@app.get("/api/trafico/slot", tags=["tráfico"])
def trafico_slot(dia: int = Query(..., ge=0, le=6), hora: int = Query(..., ge=0, le=23),
                 db: Session = Depends(get_db)):
    """RF-02: nivel típico por día y franja, por tramo."""
    reportes = ipvlib.reportes_vigentes_validados(db)
    ahora_dia, ahora_hora = _dia_hora_actual()
    aplicar = dia == ahora_dia and hora == ahora_hora
    tramos = [ipvlib.ipv_tramo(db, t, dia, hora, reportes, aplicar)
              for t in db.query(models.Tramo).order_by(models.Tramo.codigo)]
    prom = sum(t["ipv"] for t in tramos) / max(1, len(tramos))
    return {"dia": ipvlib.DIAS[dia], "dia_semana": dia, "hora": hora,
            "ipv_promedio": round(prom), **ipvlib.clasificar(prom), "tramos": tramos}


@app.get("/api/trafico/comparacion", tags=["tráfico"])
def comparar_dias(db: Session = Depends(get_db)):
    """RF-03: comportamiento de los 7 días (IPV promedio por hora)."""
    dias = []
    for d in range(7):
        serie = [round(ipvlib.ipv_promedio(db, d, h, [], aplicar_reportes=False)) for h in range(24)]
        dias.append({"dia_semana": d, "dia": ipvlib.DIAS[d], "ipv_por_hora": serie,
                     "ipv_maximo": max(serie), "hora_pico": serie.index(max(serie))})
    return {"dias": dias}


# ----------------------------------------------------------------- RF-04 a RF-06
@app.get("/api/recomendaciones/franjas", tags=["recomendaciones"])
def recomendar_franjas(dia: int = Query(..., ge=0, le=6), db: Session = Depends(get_db)):
    """RF-04: mejores franjas para salir según el histórico."""
    return {"dia": ipvlib.DIAS[dia], "franjas": ipvlib.mejores_franjas(db, dia)}


@app.get("/api/rutas", tags=["recomendaciones"])
def rutas_alternativas(db: Session = Depends(get_db)):
    """RF-05: rutas alternativas y cuándo conviene usarlas."""
    return [{
        "id": r.id, "nombre": r.nombre, "descripcion": r.descripcion,
        "franja_recomendada": r.franja_recomendada,
        "hora_inicio": r.hora_inicio, "hora_fin": r.hora_fin,
        "extra_min_flujo_libre": r.extra_min_flujo_libre,
        "ahorro_hora_pico_min": r.ahorro_hora_pico_min,
        "geometria": json.loads(r.geometria),
    } for r in db.query(models.RutaAlternativa)]


@app.get("/api/transporte", tags=["recomendaciones"])
def opciones_transporte(db: Session = Depends(get_db)):
    """RF-06: opciones de transporte de la zona."""
    return [{
        "id": o.id, "nombre": o.nombre, "tipo": o.tipo, "descripcion": o.descripcion,
        "paraderos": [p.strip() for p in o.paraderos.split(";")], "horario": o.horario,
    } for o in db.query(models.OpcionTransporte)]


# ----------------------------------------------------------------- RF-07
@app.get("/api/trafico/actual", tags=["tráfico"])
def trafico_actual(db: Session = Depends(get_db)):
    """RF-07: tráfico actual si la fuente lo permite; si no, informa que no está disponible.

    Este MVP no tiene una fuente de tráfico en tiempo real conectada, por lo que se informa
    como no disponible y se muestra el nivel TÍPICO para este día y hora.
    """
    dia, hora = _dia_hora_actual()
    tramos = [ipvlib.ipv_tramo(db, t, dia, hora) for t in db.query(models.Tramo).order_by(models.Tramo.codigo)]
    prom = sum(t["ipv"] for t in tramos) / max(1, len(tramos))
    return {
        "disponible": False,
        "mensaje": "El tráfico en tiempo real no está disponible. Mostramos el nivel típico para este día y hora.",
        "dia_semana": dia, "dia": ipvlib.DIAS[dia], "hora": hora,
        "tipico": {"ipv_promedio": round(prom), **ipvlib.clasificar(prom), "tramos": tramos},
    }


# ----------------------------------------------------------------- RF-09, RF-10
@app.get("/api/ipv", tags=["innovación"])
def indice_presion_vial(dia: int = Query(..., ge=0, le=6), hora: int = Query(..., ge=0, le=23),
                        db: Session = Depends(get_db)):
    """RF-09: IPV de 0 a 100 por tramo, día y hora."""
    return trafico_slot(dia=dia, hora=hora, db=db)


@app.get("/api/pronostico", tags=["innovación"])
def pronostico(dia: int | None = Query(None, ge=0, le=6), hora: int | None = Query(None, ge=0, le=23),
               horas: int = Query(6, ge=1, le=12), db: Session = Depends(get_db)):
    """RF-10: pronóstico de las próximas horas con indicador de confianza."""
    d0, h0 = _dia_hora_actual()
    return {"desde": {"dia": ipvlib.DIAS[dia if dia is not None else d0], "hora": hora if hora is not None else h0},
            "modelo": "estacional simple (misma hora y día de la semana del histórico)",
            "horas": ipvlib.pronostico(db, dia if dia is not None else d0, hora if hora is not None else h0, horas)}


@app.get("/api/planificador", tags=["innovación"])
def planificador(dia: int = Query(..., ge=0, le=6), hora: int = Query(..., ge=0, le=23),
                 db: Session = Depends(get_db)):
    """RF-10: «¿A qué hora salgo?»."""
    return ipvlib.planificar_salida(db, dia, hora)


# ----------------------------------------------------------------- RF-08, RF-11
class ReporteIn(BaseModel):
    tramo_codigo: str = Field(..., max_length=20)
    tipo: str = Field(..., pattern="^(trancon|accidente|obra|otro)$")
    comentario: str = Field("", max_length=280)


def _huella(request: Request) -> str:
    # Hash con sal: sirve para limitar spam sin almacenar la IP (Ley 1581 de 2012)
    ip = request.client.host if request.client else "?"
    return hashlib.sha256(f"{SAL}|{ip}|{request.headers.get('user-agent', '')}".encode()).hexdigest()[:32]


def _limitar(huella: str) -> None:
    ahora = time.time()
    cola = _hits[huella]
    while cola and ahora - cola[0] > 3600:
        cola.popleft()
    if len(cola) >= MAX_REPORTES_POR_HORA:
        raise HTTPException(429, "Has enviado muchos reportes. Intenta de nuevo más tarde.")
    cola.append(ahora)


def _reporte_out(r: models.ReporteCiudadano, tramo_codigo: str) -> dict:
    return {"id": r.id, "tramo_codigo": tramo_codigo, "tipo": r.tipo, "comentario": r.comentario,
            "creado": r.creado.isoformat(), "vigente_hasta": r.vigente_hasta.isoformat(),
            "confirmaciones": r.confirmaciones, "validado": r.validado,
            "confirmaciones_necesarias": ipvlib.CONFIRMACIONES_PARA_VALIDAR}


def _publicar(evento: dict, tareas: BackgroundTasks) -> None:
    """Sincrónica: difunde por WebSocket ahora. Asincrónica: correo/Telegram en segundo plano."""
    try:
        anyio.from_thread.run(mensajeria.conexiones.difundir, evento)
    except Exception:  # un fallo de mensajería nunca debe romper el reporte
        pass
    tareas.add_task(mensajeria.notificar, evento)


@app.websocket("/api/ws")
async def ws_eventos(ws: WebSocket):
    """Canal en vivo (solo servidor → cliente). Verifica el origen para evitar uso desde otros sitios."""
    if not mensajeria.origen_permitido(ws.headers.get("origin"), ws.headers.get("host")):
        await ws.close(code=1008)
        return
    if not await mensajeria.conexiones.conectar(ws):
        return
    try:
        while True:
            await ws.receive_text()  # se ignora lo que envíe el cliente; sirve para detectar la desconexión
    except WebSocketDisconnect:
        pass
    finally:
        mensajeria.conexiones.desconectar(ws)


@app.post("/api/reportes", status_code=201, tags=["comunidad"])
def crear_reporte(datos: ReporteIn, request: Request, tareas: BackgroundTasks, db: Session = Depends(get_db)):
    """RF-08: reportar un incidente sin registro. No ajusta el IPV hasta ser validado (RF-11)."""
    tramo = db.query(models.Tramo).filter_by(codigo=datos.tramo_codigo).first()
    if not tramo:
        raise HTTPException(404, "Tramo no encontrado")
    huella = _huella(request)
    _limitar(huella)
    ahora = datetime.now(timezone.utc)
    r = models.ReporteCiudadano(
        tramo_id=tramo.id, tipo=datos.tipo, comentario=datos.comentario.strip(),
        creado=ahora, vigente_hasta=ahora + timedelta(minutes=VIGENCIA_REPORTE_MIN),
        huella=huella,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    _publicar(mensajeria.crear_evento("reporte_nuevo", r.id, tramo.codigo, r.tipo, r.validado), tareas)
    return _reporte_out(r, tramo.codigo)


@app.get("/api/reportes", tags=["comunidad"])
def listar_reportes(db: Session = Depends(get_db)):
    """Reportes vigentes (validados o pendientes de validar)."""
    ahora = datetime.now(timezone.utc)
    salida = []
    for r in db.query(models.ReporteCiudadano).order_by(models.ReporteCiudadano.creado.desc()).limit(100):
        vig = r.vigente_hasta if r.vigente_hasta.tzinfo else r.vigente_hasta.replace(tzinfo=timezone.utc)
        if vig > ahora:
            tramo = db.get(models.Tramo, r.tramo_id)
            salida.append(_reporte_out(r, tramo.codigo))
    return salida


@app.post("/api/reportes/{reporte_id}/confirmar", tags=["comunidad"])
def confirmar_reporte(reporte_id: int, request: Request, tareas: BackgroundTasks, db: Session = Depends(get_db)):
    """RF-11: otras personas confirman; con las confirmaciones necesarias el reporte se valida."""
    r = db.get(models.ReporteCiudadano, reporte_id)
    if not r:
        raise HTTPException(404, "Reporte no encontrado")
    vig = r.vigente_hasta if r.vigente_hasta.tzinfo else r.vigente_hasta.replace(tzinfo=timezone.utc)
    if vig <= datetime.now(timezone.utc):
        raise HTTPException(409, "El reporte ya venció")
    huella = _huella(request)
    if huella == r.huella:
        raise HTTPException(409, "No puedes confirmar tu propio reporte")
    clave = f"conf:{reporte_id}:{huella}"
    if clave in _hits and _hits[clave]:
        raise HTTPException(409, "Ya confirmaste este reporte")
    _hits[clave].append(time.time())
    r.confirmaciones += 1
    recien_validado = False
    if r.confirmaciones >= ipvlib.CONFIRMACIONES_PARA_VALIDAR and not r.validado:
        r.validado = True
        recien_validado = True
    db.commit()
    tramo = db.get(models.Tramo, r.tramo_id)
    tipo_evento = "reporte_validado" if recien_validado else "reporte_confirmado"
    _publicar(mensajeria.crear_evento(tipo_evento, r.id, tramo.codigo, r.tipo, r.validado), tareas)
    return _reporte_out(r, tramo.codigo)


# ----------------------------------------------------------------- web estática (un solo servicio, ej. Render)
# Si existe la compilación del front-end (carpeta static/), la API la sirve en el mismo origen:
# así /api y /api/ws funcionan sin configurar CORS y el HTTPS lo pone la plataforma.
mimetypes.add_type("application/manifest+json", ".webmanifest")
STATIC_DIR = Path(os.getenv("STATIC_DIR", str(Path(__file__).resolve().parent.parent / "static")))

if (STATIC_DIR / "index.html").is_file():
    _BASE = STATIC_DIR.resolve()
    _SIN_CACHE = {"index.html", "sw.js", "registerSW.js", "manifest.webmanifest"}

    @app.get("/{ruta:path}", include_in_schema=False)
    def sitio_estatico(ruta: str):
        if ruta == "api" or ruta.startswith("api/"):
            raise HTTPException(404, "Recurso no encontrado")
        candidato = (_BASE / ruta).resolve()
        if ruta and candidato.is_file() and _BASE in candidato.parents:  # nunca sale de la carpeta (path traversal)
            archivo = candidato
        elif "." in ruta.rsplit("/", 1)[-1]:
            raise HTTPException(404, "Archivo no encontrado")  # un .js o .png inexistente no debe devolver la página
        else:
            archivo = _BASE / "index.html"  # rutas de la aplicación de una página (SPA)
        if archivo.name in _SIN_CACHE or archivo.name.startswith("workbox-"):
            cache = "no-cache"
        elif "assets" in archivo.parts:
            cache = "public, max-age=31536000, immutable"  # archivos con hash en el nombre
        else:
            cache = "public, max-age=3600"
        return FileResponse(archivo, headers={"Cache-Control": cache})
