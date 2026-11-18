"""Índice de Presión Vial (IPV), pronóstico y planificador (RF-09, RF-10, RF-11).

IPV = nivel histórico típico (0-100) del tramo para ese día y hora
      + ajuste por reportes ciudadanos validados y vigentes (RF-11).

Clasificación (KAN-37): fluido 0-33, moderado 34-66, congestionado 67-100.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from . import models

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Puntos que suma cada tipo de reporte validado al IPV del tramo
AJUSTE_POR_TIPO = {"accidente": 15.0, "trancon": 10.0, "obra": 8.0, "otro": 3.0}
AJUSTE_MAXIMO = 25.0
# Configurable: en una demostración en clase puede ponerse en 1 (variable CONFIRMACIONES_PARA_VALIDAR)
CONFIRMACIONES_PARA_VALIDAR = max(1, int(os.getenv("CONFIRMACIONES_PARA_VALIDAR", "2")))

# Cuánto se alarga el tiempo de viaje con IPV=100 respecto del flujo libre
FACTOR_RETRASO_MAX = 2.5


def clasificar(ipv: float) -> dict:
    """Color y texto del nivel (el color nunca es el único indicador: RNF de accesibilidad)."""
    if ipv <= 33:
        return {"nivel": "fluido", "etiqueta": "Fluido", "color": "#2e8540"}
    if ipv <= 66:
        return {"nivel": "moderado", "etiqueta": "Moderado", "color": "#e0a800"}
    return {"nivel": "congestionado", "etiqueta": "Congestionado", "color": "#c0392b"}


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def reportes_vigentes_validados(db: Session, ahora: datetime | None = None) -> list[models.ReporteCiudadano]:
    ahora = ahora or _ahora()
    todos = db.query(models.ReporteCiudadano).filter(models.ReporteCiudadano.validado.is_(True)).all()
    return [r for r in todos if _aware(r.vigente_hasta) > ahora]


def ajuste_por_reportes(reportes: Iterable[models.ReporteCiudadano], tramo_id: int) -> float:
    total = sum(AJUSTE_POR_TIPO.get(r.tipo, 3.0) for r in reportes if r.tramo_id == tramo_id)
    return min(total, AJUSTE_MAXIMO)


def nivel_historico(db: Session, tramo_id: int, dia: int, hora: int) -> models.RegistroTrafico | None:
    return (db.query(models.RegistroTrafico)
            .filter_by(tramo_id=tramo_id, dia_semana=dia, hora=hora).first())


def ipv_tramo(db: Session, tramo: models.Tramo, dia: int, hora: int,
              reportes: list[models.ReporteCiudadano] | None = None,
              aplicar_reportes: bool = True) -> dict:
    reg = nivel_historico(db, tramo.id, dia, hora)
    base = reg.nivel if reg else 0.0
    ajuste = 0.0
    if aplicar_reportes:
        if reportes is None:
            reportes = reportes_vigentes_validados(db)
        ajuste = ajuste_por_reportes(reportes, tramo.id)
    ipv = max(0.0, min(100.0, base + ajuste))
    return {
        "tramo_codigo": tramo.codigo,
        "tramo": tramo.nombre,
        "ipv": round(ipv),
        "base": round(base, 1),
        "ajuste_comunidad": round(ajuste, 1),
        "ajustado_por_comunidad": ajuste > 0,
        **clasificar(ipv),
    }


def ipv_promedio(db: Session, dia: int, hora: int, reportes=None, aplicar_reportes=True) -> float:
    tramos = db.query(models.Tramo).all()
    if not tramos:
        return 0.0
    if aplicar_reportes and reportes is None:
        reportes = reportes_vigentes_validados(db)
    vals = [ipv_tramo(db, t, dia, hora, reportes, aplicar_reportes)["ipv"] for t in tramos]
    return sum(vals) / len(vals)


def tiempo_viaje_min(db: Session, ipv_prom: float) -> float:
    libre = sum(t.tiempo_libre_min for t in db.query(models.Tramo).all())
    return libre * (1 + FACTOR_RETRASO_MAX * ipv_prom / 100.0)


def confianza(db: Session, dia: int, hora: int) -> float:
    """Confianza 0-1 según el número de muestras y la variabilidad del histórico."""
    regs = db.query(models.RegistroTrafico).filter_by(dia_semana=dia, hora=hora).all()
    if not regs:
        return 0.0
    muestras = sum(r.muestras for r in regs) / len(regs)
    desv = sum(r.desviacion for r in regs) / len(regs)
    por_muestras = min(1.0, muestras / 8.0)
    por_variabilidad = max(0.2, 1.0 - desv / 40.0)
    return round(max(0.1, min(0.95, por_muestras * por_variabilidad)), 2)


def pronostico(db: Session, dia: int, hora: int, horas: int = 6) -> list[dict]:
    """Modelo estacional simple: el IPV esperado es el de la misma hora y día de la semana
    en el histórico (más el ajuste de reportes vigentes, que decae con la distancia)."""
    reportes = reportes_vigentes_validados(db)
    resultado = []
    for i in range(horas):
        total = dia * 24 + hora + i
        d, h = (total // 24) % 7, total % 24
        # Los reportes solo influyen en la próxima hora (son información de "ahora")
        aplicar = i == 0
        ipv = ipv_promedio(db, d, h, reportes, aplicar_reportes=aplicar)
        resultado.append({
            "dia_semana": d, "dia": DIAS[d], "hora": h,
            "ipv": round(ipv), "confianza": confianza(db, d, h), **clasificar(ipv),
        })
    return resultado


def planificar_salida(db: Session, dia: int, hora_deseada: int, ventana: int = 3) -> dict:
    """«¿A qué hora salgo?»: busca la mejor franja cerca de la hora deseada y estima el ahorro
    frente a salir en esa hora deseada y frente a la hora pico del día."""
    reportes = reportes_vigentes_validados(db)
    candidatos = []
    for delta in range(-ventana, ventana + 1):
        total = dia * 24 + hora_deseada + delta
        if total < dia * 24 or total >= (dia + 1) * 24:
            continue  # se mantiene dentro del mismo día
        h = total % 24
        ipv = ipv_promedio(db, dia, h, reportes, aplicar_reportes=(delta == 0))
        candidatos.append({"hora": h, "ipv": ipv, "minutos": tiempo_viaje_min(db, ipv)})

    deseada = next(c for c in candidatos if c["hora"] == hora_deseada)
    mejor = min(candidatos, key=lambda c: (c["minutos"], abs(c["hora"] - hora_deseada)))

    pico = max(((h, ipv_promedio(db, dia, h, reportes, False)) for h in range(5, 22)), key=lambda x: x[1])
    minutos_pico = tiempo_viaje_min(db, pico[1])

    rutas = db.query(models.RutaAlternativa).all()
    ruta_sugerida = None
    mejor_ruta_min = None
    libre_total = sum(t.tiempo_libre_min for t in db.query(models.Tramo).all())
    for r in rutas:
        # La alternativa se recomienda dentro de su franja y cuando la avenida está pesada
        if r.hora_inicio <= mejor["hora"] < r.hora_fin and mejor["ipv"] >= 40 and dia < 5:
            minutos = (libre_total + r.extra_min_flujo_libre) * (1 + 0.4 * mejor["ipv"] / 100.0)
            if minutos < mejor["minutos"] and (mejor_ruta_min is None or minutos < mejor_ruta_min):
                ruta_sugerida, mejor_ruta_min = r, minutos

    minutos_final = mejor_ruta_min if ruta_sugerida else mejor["minutos"]
    ahorro_vs_deseada = max(0.0, deseada["minutos"] - minutos_final)
    ahorro_vs_pico = max(0.0, minutos_pico - minutos_final)

    if mejor["hora"] == hora_deseada and not ruta_sugerida:
        mensaje = f"Tu hora ({hora_deseada:02d}:00) ya es de las mejores del rango; salir entonces está bien."
    else:
        mensaje = f"Sal a las {mejor['hora']:02d}:00" + (f" por «{ruta_sugerida.nombre}»" if ruta_sugerida else "") + \
                  f" y ahorra unos {round(ahorro_vs_deseada)} min frente a salir a las {hora_deseada:02d}:00."

    return {
        "dia_semana": dia, "dia": DIAS[dia], "hora_deseada": hora_deseada,
        "hora_sugerida": mejor["hora"],
        "ipv_hora_sugerida": round(mejor["ipv"]), **clasificar(mejor["ipv"]),
        "ruta_sugerida": ruta_sugerida.nombre if ruta_sugerida else "Avenida Pradilla",
        "tiempo_estimado_min": round(minutos_final),
        "tiempo_hora_deseada_min": round(deseada["minutos"]),
        "ahorro_vs_hora_deseada_min": round(ahorro_vs_deseada),
        "hora_pico": pico[0], "ahorro_vs_hora_pico_min": round(ahorro_vs_pico),
        "confianza": confianza(db, dia, mejor["hora"]),
        "mensaje": mensaje,
        "alternativas": [{"hora": c["hora"], "ipv": round(c["ipv"]), "minutos": round(c["minutos"])} for c in candidatos],
    }


def mejores_franjas(db: Session, dia: int, cantidad: int = 4) -> list[dict]:
    """RF-04: mejores horas para salir (entre las 5:00 y las 22:00)."""
    horas = []
    for h in range(5, 23):
        horas.append((h, ipv_promedio(db, dia, h, [], aplicar_reportes=False)))
    horas.sort(key=lambda x: x[1])
    return [{"hora": h, "ipv": round(v), **clasificar(v)} for h, v in horas[:cantidad]]
