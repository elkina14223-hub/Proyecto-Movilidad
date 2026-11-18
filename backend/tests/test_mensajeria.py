import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/msg.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from app import mensajeria  # noqa: E402
from app.main import _hits, app  # noqa: E402


@pytest.fixture
def client():
    _hits.clear()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def salidas(monkeypatch):
    """Registra lo que saldría por Telegram y por correo sin enviarlo de verdad."""
    reg = {"telegram": [], "correo": []}
    monkeypatch.setattr(mensajeria, "enviar_telegram", lambda t: reg["telegram"].append(t) or True)
    monkeypatch.setattr(mensajeria, "enviar_correo", lambda a, c: reg["correo"].append((a, c)) or True)
    return reg


# ------------------------------------------------------------ sincrónica: WebSocket
def test_websocket_recibe_reporte_nuevo_sin_datos_personales(client, salidas):
    with client.websocket_connect("/api/ws") as ws:
        r = client.post("/api/reportes", json={"tramo_codigo": "T2", "tipo": "trancon", "comentario": "secreto-123"},
                        headers={"user-agent": "ws-a"})
        assert r.status_code == 201
        ev = ws.receive_json()
    assert ev["tipo"] == "reporte_nuevo" and ev["tramo_codigo"] == "T2" and ev["validado"] is False
    assert "secreto-123" not in str(ev) and "comentario" not in ev
    assert salidas["telegram"] == [] and salidas["correo"] == []  # solo se avisa al equipo al validar


def test_websocket_difunde_a_varios_clientes(client, salidas):
    with client.websocket_connect("/api/ws") as a, client.websocket_connect("/api/ws") as b:
        client.post("/api/reportes", json={"tramo_codigo": "T1", "tipo": "obra"}, headers={"user-agent": "ws-b"})
        assert a.receive_json()["tipo"] == "reporte_nuevo"
        assert b.receive_json()["tipo"] == "reporte_nuevo"


def test_validacion_emite_evento_y_notifica_una_sola_vez(client, salidas):
    with client.websocket_connect("/api/ws") as ws:
        rep = client.post("/api/reportes", json={"tramo_codigo": "T3", "tipo": "accidente"},
                          headers={"user-agent": "autor-1"}).json()
        assert ws.receive_json()["tipo"] == "reporte_nuevo"
        client.post(f"/api/reportes/{rep['id']}/confirmar", headers={"user-agent": "c1"})
        assert ws.receive_json()["tipo"] == "reporte_confirmado"
        client.post(f"/api/reportes/{rep['id']}/confirmar", headers={"user-agent": "c2"})
        ev = ws.receive_json()
        assert ev["tipo"] == "reporte_validado" and ev["validado"] is True
        # Una tercera confirmación no vuelve a disparar la alerta al equipo
        client.post(f"/api/reportes/{rep['id']}/confirmar", headers={"user-agent": "c3"})
        assert ws.receive_json()["tipo"] == "reporte_confirmado"
    assert len(salidas["telegram"]) == 1 and len(salidas["correo"]) == 1
    assert "Accidente" in salidas["telegram"][0] and "T3" in salidas["telegram"][0]
    assert salidas["correo"][0][0].startswith("[Pradilla]")


def test_websocket_rechaza_origen_no_permitido(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws", headers={"origin": "https://sitio-malicioso.example"}):
            pass


def test_websocket_acepta_origen_permitido(client, monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://movilidad.ejemplo.co")
    with client.websocket_connect("/api/ws", headers={"origin": "https://movilidad.ejemplo.co"}):
        assert len(mensajeria.conexiones.activas) >= 1


def test_websocket_limite_de_conexiones(client, monkeypatch):
    monkeypatch.setattr(mensajeria, "MAX_CONEXIONES", 0)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws"):
            pass


def test_se_libera_la_conexion_al_cerrar(client):
    antes = len(mensajeria.conexiones.activas)
    with client.websocket_connect("/api/ws"):
        pass
    assert len(mensajeria.conexiones.activas) == antes


def test_fallo_de_mensajeria_no_rompe_el_reporte(client, monkeypatch):
    async def falla(_):
        raise RuntimeError("caído")
    monkeypatch.setattr(mensajeria.conexiones, "difundir", falla)
    r = client.post("/api/reportes", json={"tramo_codigo": "T1", "tipo": "otro"}, headers={"user-agent": "ws-z"})
    assert r.status_code == 201


# ------------------------------------------------------------ sincrónica: Telegram
def test_telegram_envia_texto_plano_y_recorta(monkeypatch):
    llamadas = []

    class Resp:
        def raise_for_status(self): pass

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN-SECRETO")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    monkeypatch.setattr(mensajeria.httpx, "post", lambda url, **kw: llamadas.append((url, kw)) or Resp())
    assert mensajeria.enviar_telegram("x" * 5000) is True
    url, kw = llamadas[0]
    assert url.endswith("/sendMessage") and "parse_mode" not in kw["json"]
    assert len(kw["json"]["text"]) == 1000 and kw["json"]["chat_id"] == "42"


def test_telegram_sin_configurar_o_con_error_no_lanza(monkeypatch, caplog):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    assert mensajeria.enviar_telegram("hola") is False

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN-SECRETO")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")

    def boom(*a, **k):
        raise mensajeria.httpx.ConnectError("sin red https://api.telegram.org/botTOKEN-SECRETO/sendMessage")
    monkeypatch.setattr(mensajeria.httpx, "post", boom)
    with caplog.at_level("WARNING"):
        assert mensajeria.enviar_telegram("hola") is False
    assert "TOKEN-SECRETO" not in caplog.text  # el token nunca se escribe en los registros


# ------------------------------------------------------------ asincrónica: correo
class FakeSMTP:
    instancias = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port, self.pasos, self.mensaje = host, port, [], None
        FakeSMTP.instancias.append(self)

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def starttls(self, context=None): self.pasos.append("starttls")
    def login(self, u, p): self.pasos.append(f"login:{u}")
    def send_message(self, m): self.mensaje = m; self.pasos.append("send")


def test_correo_usa_starttls_antes_de_autenticar(monkeypatch):
    FakeSMTP.instancias.clear()
    monkeypatch.setattr(mensajeria.smtplib, "SMTP", FakeSMTP)
    for k, v in {"SMTP_HOST": "smtp.ejemplo.com", "SMTP_PORT": "587", "SMTP_USER": "bot@ejemplo.com",
                 "SMTP_PASSWORD": "clave", "ALERT_EMAILS": "a@x.co, b@x.co"}.items():
        monkeypatch.setenv(k, v)
    assert mensajeria.enviar_correo("Asunto", "Cuerpo") is True
    s = FakeSMTP.instancias[0]
    assert s.pasos == ["starttls", "login:bot@ejemplo.com", "send"]  # el TLS va primero
    assert s.mensaje["To"] == "a@x.co, b@x.co"


def test_correo_no_permite_inyeccion_de_cabeceras(monkeypatch):
    FakeSMTP.instancias.clear()
    monkeypatch.setattr(mensajeria.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setenv("SMTP_HOST", "smtp.ejemplo.com")
    monkeypatch.setenv("ALERT_EMAILS", "a@x.co")
    mensajeria.enviar_correo("Hola\r\nBcc: victima@x.co", "texto")
    m = FakeSMTP.instancias[0].mensaje
    assert m["Bcc"] is None and "\n" not in m["Subject"]


def test_correo_sin_configurar_o_con_error(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert mensajeria.enviar_correo("a", "b") is False

    class Roto(FakeSMTP):
        def __init__(self, *a, **k): raise OSError("sin red")
    monkeypatch.setenv("SMTP_HOST", "x")
    monkeypatch.setenv("ALERT_EMAILS", "a@x.co")
    monkeypatch.setattr(mensajeria.smtplib, "SMTP", Roto)
    assert mensajeria.enviar_correo("a", "b") is False


# ------------------------------------------------------------ estado
def test_estado_en_entorno_no_expone_direcciones(client, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.ejemplo.com")
    monkeypatch.setenv("ALERT_EMAILS", "privado@ejemplo.com,otro@ejemplo.com")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "TOKEN-SECRETO")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "42")
    txt = client.get("/api/entorno").text
    d = client.get("/api/entorno").json()["mensajeria"]
    assert d["asincronica"]["correo"]["configurado"] is True and d["asincronica"]["correo"]["destinatarios"] == 2
    assert d["sincronica"]["telegram"]["configurado"] is True
    assert "privado@ejemplo.com" not in txt and "TOKEN-SECRETO" not in txt
