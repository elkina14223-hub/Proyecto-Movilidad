"""Mensajería del sistema.

SINCRÓNICA (tiempo real, la persona está conectada):
  - WebSocket (WSS en producción): la web recibe al instante reportes nuevos y validados.
  - Telegram (integración móvil): aviso inmediato al chat del equipo vía la API de Bots.
ASINCRÓNICA (no requiere que el destinatario esté conectado):
  - Correo electrónico por SMTP con STARTTLS. El equipo lo lee después con IMAP o POP3.

Principios de seguridad: los eventos en vivo no llevan datos personales ni el texto libre del
reporte (el cliente consulta la API); las notificaciones salen en segundo plano para no demorar
la respuesta; los secretos (clave SMTP, token de Telegram) solo viven en variables de entorno.
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from urllib.parse import urlparse

import httpx
from fastapi import WebSocket

log = logging.getLogger("mensajeria")

MAX_CONEXIONES = int(os.getenv("WS_MAX_CONEXIONES", "200"))


# ----------------------------------------------------------------- sincrónica: WebSocket
class Conexiones:
    """Conjunto de clientes conectados por WebSocket (solo servidor → cliente)."""

    def __init__(self) -> None:
        self.activas: set[WebSocket] = set()

    async def conectar(self, ws: WebSocket) -> bool:
        if len(self.activas) >= MAX_CONEXIONES:
            await ws.close(code=1013)  # intente más tarde
            return False
        await ws.accept()
        self.activas.add(ws)
        return True

    def desconectar(self, ws: WebSocket) -> None:
        self.activas.discard(ws)

    async def difundir(self, evento: dict) -> None:
        texto = json.dumps(evento, ensure_ascii=False)
        for ws in list(self.activas):
            try:
                await ws.send_text(texto)
            except Exception:
                self.activas.discard(ws)


conexiones = Conexiones()


def origen_permitido(origen: str | None, host: str | None = None) -> bool:
    """Evita que otros sitios abran el WebSocket desde el navegador de una persona (CSWSH).

    Se acepta el mismo sitio (el Origin coincide con el Host al que se conectó el navegador),
    lo que funciona en cualquier dominio sin configurar nada, y los orígenes listados en CORS_ORIGINS.
    """
    if not origen:
        return True  # clientes que no son navegadores (pruebas, curl) no envían Origin
    if host and urlparse(origen).netloc == host:
        return True
    permitidos = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:8080").split(",") if o.strip()]
    extra = os.getenv("PUBLIC_ORIGIN")
    if extra:
        permitidos.append(extra.strip())
    return origen in permitidos


def crear_evento(tipo: str, reporte_id: int, tramo_codigo: str, reporte_tipo: str, validado: bool) -> dict:
    # Sin comentario ni datos de la persona: el cliente pide el detalle por la API
    return {
        "tipo": tipo, "reporte_id": reporte_id, "tramo_codigo": tramo_codigo,
        "reporte_tipo": reporte_tipo, "validado": validado,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# ----------------------------------------------------------------- sincrónica: Telegram
def telegram_configurado() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def enviar_telegram(texto: str) -> bool:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat):
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": texto[:1000], "disable_web_page_preview": True},  # texto plano: sin parse_mode
            timeout=8,
        )
        r.raise_for_status()
        return True
    except Exception as e:  # nunca imprimir la URL: contiene el token
        log.warning("Telegram no disponible: %s", type(e).__name__)
        return False


# ----------------------------------------------------------------- asincrónica: correo
def destinatarios() -> list[str]:
    return [d.strip() for d in os.getenv("ALERT_EMAILS", "").split(",") if d.strip()]


def correo_configurado() -> bool:
    return bool(os.getenv("SMTP_HOST") and destinatarios())


def enviar_correo(asunto: str, cuerpo: str) -> bool:
    if not correo_configurado():
        return False
    host = os.environ["SMTP_HOST"]
    puerto = int(os.getenv("SMTP_PORT", "587"))
    usuario, clave = os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD")
    remitente = os.getenv("SMTP_FROM") or usuario or "no-responder@localhost"

    msg = EmailMessage()  # EmailMessage rechaza saltos de línea en cabeceras (evita inyección)
    msg["Subject"] = " ".join(asunto.split())[:120]
    msg["From"] = remitente
    msg["To"] = ", ".join(destinatarios())
    msg.set_content(cuerpo)
    try:
        if puerto == 465:
            with smtplib.SMTP_SSL(host, puerto, timeout=10, context=ssl.create_default_context()) as s:
                if usuario and clave:
                    s.login(usuario, clave)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, puerto, timeout=10) as s:
                s.starttls(context=ssl.create_default_context())  # cifra el canal con TLS
                if usuario and clave:
                    s.login(usuario, clave)
                s.send_message(msg)
        return True
    except Exception as e:
        log.warning("Correo no enviado: %s", type(e).__name__)
        return False


# ----------------------------------------------------------------- orquestación
ETIQUETA = {"trancon": "Trancón", "accidente": "Accidente", "obra": "Obra", "otro": "Otro"}


def notificar(evento: dict) -> None:
    """Se ejecuta en segundo plano (BackgroundTasks) después de responder a la persona."""
    if evento.get("tipo") != "reporte_validado":
        return  # solo se avisa al equipo cuando la comunidad validó el reporte
    tipo = ETIQUETA.get(evento.get("reporte_tipo", ""), "Incidente")
    tramo = evento.get("tramo_codigo", "?")
    texto = f"Reporte validado por la comunidad: {tipo} en el tramo {tramo} de la Av. Pradilla (Chía)."
    enviar_telegram(texto)
    enviar_correo(f"[Pradilla] {tipo} validado en {tramo}", texto + "\n\nEl índice de presión vial de ese tramo se ajusta mientras el reporte esté vigente (60 min).")


def estado() -> dict:
    return {
        "sincronica": {
            "websocket": {"activo": True, "conexiones": len(conexiones.activas), "protocolo": "WebSocket (wss:// con HTTPS)"},
            "telegram": {"configurado": telegram_configurado()},
        },
        "asincronica": {
            "correo": {
                "configurado": correo_configurado(),
                "envio": "SMTP con STARTTLS",
                "lectura": "IMAP o POP3 desde el buzón del equipo",
                "destinatarios": len(destinatarios()),  # solo la cantidad, nunca las direcciones
            }
        },
    }
