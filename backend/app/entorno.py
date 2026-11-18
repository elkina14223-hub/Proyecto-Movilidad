"""Estado del entorno de publicación: servidor, hosting, dominio y certificado TLS.

Lee el certificado real que usa nginx (CERT_FILE) y lo interpreta. Los datos del hosting
(proveedor, región) vienen de variables de entorno porque el servidor no puede adivinarlos.
Nunca se expone la clave privada ni versiones de software (RNF-SEG-05).
"""
from __future__ import annotations

import ipaddress
import os
import socket
import ssl
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.x509.oid import NameOID

INICIO = time.time()

# Identificadores estándar (CA/Browser Forum) de la validación del certificado
_POLITICAS = {
    "2.23.140.1.2.1": ("dominio", "Validación de dominio (DV)", "≈ 3 meses (Let's Encrypt: 90 días)"),
    "2.23.140.1.2.2": ("organizacional", "Validación organizacional (OV)", "≈ 1 año"),
    "2.23.140.1.1": ("extendido", "Validación extendida (EV)", "≈ 1 año"),
}


def _nombre(attrs, oid) -> str | None:
    v = attrs.get_attributes_for_oid(oid)
    return v[0].value if v else None


def _tipo(cert: x509.Certificate) -> dict:
    if cert.issuer == cert.subject:
        return {"codigo": "autofirmado", "nombre": "Autofirmado (solo desarrollo, no es de confianza)", "duracion_tipica": "—"}
    try:
        ext = cert.extensions.get_extension_for_class(x509.CertificatePolicies).value
        for pol in ext:
            dato = _POLITICAS.get(pol.policy_identifier.dotted_string)
            if dato:
                return {"codigo": dato[0], "nombre": dato[1], "duracion_tipica": dato[2]}
    except x509.ExtensionNotFound:
        pass
    return {"codigo": "desconocido", "nombre": "Tipo no identificado", "duracion_tipica": "—"}


def interpretar(cert: x509.Certificate) -> dict:
    desde = cert.not_valid_before_utc
    hasta = cert.not_valid_after_utc
    ahora = datetime.now(timezone.utc)
    dias = (hasta - ahora).days
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
    except x509.ExtensionNotFound:
        san = []
    tipo = _tipo(cert)
    if ahora > hasta:
        estado = "vencido"
    elif tipo["codigo"] == "autofirmado":
        estado = "no_confiable"
    elif dias <= 14:
        estado = "por_vencer"
    else:
        estado = "vigente"
    return {
        "disponible": True,
        "estado": estado,
        "tipo": tipo,
        "sujeto": _nombre(cert.subject, NameOID.COMMON_NAME),
        "organizacion": _nombre(cert.subject, NameOID.ORGANIZATION_NAME),
        "emisor": _nombre(cert.issuer, NameOID.ORGANIZATION_NAME) or _nombre(cert.issuer, NameOID.COMMON_NAME),
        "dominios": san,
        "valido_desde": desde.isoformat(),
        "valido_hasta": hasta.isoformat(),
        "dias_restantes": dias,
        "algoritmo_clave": type(cert.public_key()).__name__.replace("_", "").replace("PublicKey", ""),
        "huella_sha256": cert.fingerprint(hashes.SHA256()).hex(),
    }


def leer_certificado(ruta: str | None) -> dict:
    if not ruta or not Path(ruta).is_file():
        return {"disponible": False, "motivo": "No se encontró el archivo del certificado en el servidor."}
    try:
        cert = x509.load_pem_x509_certificate(Path(ruta).read_bytes())
    except Exception:
        return {"disponible": False, "motivo": "El archivo del certificado no se pudo leer."}
    return {**interpretar(cert), "origen": "archivo del servidor"}


# ---- Certificado que presenta el dominio público (cuando lo administra la plataforma, ej. Render) ----
_cache_remoto: dict[tuple, tuple[float, dict | None]] = {}
_candado = threading.Lock()
TTL_OK, TTL_FALLO = 600, 60  # segundos


def consultar_tls_remoto(host: str, puerto: int = 443, cafile: str | None = None) -> dict | None:
    """Abre una conexión TLS al dominio PÚBLICO y devuelve certificado, protocolo y cifrado negociados.

    Seguridad: el host sale de la configuración del servidor (nunca de lo que envía quien navega),
    la cadena de confianza se VERIFICA (si no es válida, no se muestra como válida), el tiempo de
    espera es corto y el resultado se guarda en memoria para no repetir la consulta en cada visita.
    """
    clave = (host, puerto)
    ahora = time.time()
    with _candado:
        previo = _cache_remoto.get(clave)
        if previo and previo[0] > ahora:
            return previo[1]
    try:
        contexto = ssl.create_default_context(cafile=cafile)
        with socket.create_connection((host, puerto), timeout=4) as sock:
            with contexto.wrap_socket(sock, server_hostname=host) as s:
                datos = {"der": s.getpeercert(binary_form=True), "protocolo": s.version(), "cifrado": (s.cipher() or ("—",))[0]}
    except Exception:
        datos = None
    with _candado:
        _cache_remoto[clave] = (ahora + (TTL_OK if datos else TTL_FALLO), datos)
    return datos


def host_publico_configurado() -> str | None:
    return os.getenv("CERT_REMOTE_HOST") or os.getenv("RENDER_EXTERNAL_HOSTNAME") or None


def _es_local(host: str) -> bool:
    h = host.split(":")[0].lower()
    if h in ("localhost", "") or h.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(h)
        return ip.is_private or ip.is_loopback
    except ValueError:
        return False


def _servidor_web(protocolo_tls: str | None) -> str:
    # nginx envía los encabezados X-TLS-*; en una plataforma administrada el proxy es de la plataforma
    if protocolo_tls:
        return "nginx (versión oculta)"
    plataforma = os.getenv("TLS_GESTIONADO_POR")
    if plataforma:
        return f"Uvicorn (FastAPI) detrás del proxy de {plataforma}"
    return "Aplicación directa, sin nginx (solo desarrollo)"


def estado_entorno(host_cabecera: str, esquema: str, protocolo_tls: str | None, cifrado: str | None, db_ok: bool) -> dict:
    host = (host_cabecera or "").split(":")[0]
    es_ip = False
    try:
        ipaddress.ip_address(host)
        es_ip = True
    except ValueError:
        pass
    dominio_propio = bool(host) and not _es_local(host) and not es_ip

    cert = leer_certificado(os.getenv("CERT_FILE", "/etc/nginx/certs/fullchain.pem"))
    remoto = None
    if not cert.get("disponible"):
        # Sin archivo local (plataforma administrada): se lee el certificado que el dominio público presenta
        host_remoto = host_publico_configurado()
        if host_remoto:
            remoto = consultar_tls_remoto(host_remoto, int(os.getenv("CERT_REMOTE_PORT", "443")))
            if remoto:
                cert = {**interpretar(x509.load_der_x509_certificate(remoto["der"])), "origen": f"consultado al dominio público ({host_remoto})"}
    cert["gestionado_por"] = os.getenv("TLS_GESTIONADO_POR") or None
    if not cert.get("disponible") and cert["gestionado_por"]:
        cert["motivo"] = f"El certificado lo emite y renueva {cert['gestionado_por']} y aún no se pudo consultar."
    cubre_dominio = bool(cert.get("disponible")) and any(
        d == host or (d.startswith("*.") and host.endswith(d[1:])) for d in cert.get("dominios", [])
    )

    segundos = int(time.time() - INICIO)
    return {
        "servidor": {
            "estado": "operando" if db_ok else "degradado",
            "base_de_datos": "conectada" if db_ok else "sin conexión",
            # nginx envía los encabezados X-TLS-*; sin ellos la API se está sirviendo directamente
            "servidor_web": _servidor_web(protocolo_tls),
            "en_linea_desde_segundos": segundos,
        },
        "hosting": {
            "estado": "operando",
            "proveedor": os.getenv("HOSTING_PROVIDER", "Sin configurar"),
            "region": os.getenv("HOSTING_REGION", "Sin configurar"),
            "tipo": os.getenv("HOSTING_TYPE", "Sin configurar"),
            "configurado": os.getenv("HOSTING_PROVIDER") is not None,
        },
        "dominio": {
            "estado": "operando" if dominio_propio else "local",
            "nombre": host or "—",
            "es_dominio_publico": dominio_propio,
            "certificado_cubre_dominio": cubre_dominio,
        },
        "tls": {
            "https_activo": esquema == "https",
            "protocolo": protocolo_tls or (remoto or {}).get("protocolo") or "—",
            "cifrado": cifrado or (remoto or {}).get("cifrado") or "—",
            "hsts": "max-age=31536000; includeSubDomains",
            "redireccion_http": "301",
        },
        "certificado": cert,
    }
