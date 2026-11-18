import os
import tempfile
from pathlib import Path

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/render.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from app import database, mensajeria, migrate  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------- DATABASE_URL de Render
def test_normaliza_url_de_render_a_psycopg():
    assert database.normalizar_url("postgres://u:p@h:5432/d") == "postgresql+psycopg://u:p@h:5432/d"
    assert database.normalizar_url("postgresql://u:p@h/d") == "postgresql+psycopg://u:p@h/d"
    assert database.normalizar_url("postgresql+psycopg://u:p@h/d") == "postgresql+psycopg://u:p@h/d"
    assert database.normalizar_url("sqlite:///x.db") == "sqlite:///x.db"


# ---------------------------------------------------- PostGIS opcional
class _Dialecto:
    name = "postgresql"


class _Con:
    def __init__(self, motor): self.motor = motor
    def __enter__(self): return self
    def __exit__(self, *a): return False

    def execute(self, sentencia, params=None):
        txt = str(sentencia)
        if "SELECT nombre" in txt:
            return []
        if "INSERT INTO schema_migrations" in txt:
            self.motor.registradas.append(params["n"])
        return []

    def exec_driver_sql(self, sql):
        if "postgis" in sql.lower() or "geom" in sql.lower():
            if self.motor.sin_postgis:
                raise RuntimeError("extension postgis no disponible")
        self.motor.ejecutadas.append(sql[:20])


class _Motor:
    dialect = _Dialecto()

    def __init__(self, sin_postgis):
        self.sin_postgis, self.registradas, self.ejecutadas = sin_postgis, [], []

    def begin(self): return _Con(self)


def test_migraciones_continuan_si_no_hay_postgis():
    motor = _Motor(sin_postgis=True)
    assert migrate.aplicar(motor) == []  # las dos son opcionales: se omiten sin romper el arranque
    assert motor.registradas == []


def test_migraciones_se_aplican_si_hay_postgis():
    motor = _Motor(sin_postgis=False)
    assert migrate.aplicar(motor) == ["001_postgis.sql", "002_geom_tramos.sql"]


def test_migracion_no_opcional_si_falla(monkeypatch, tmp_path):
    (tmp_path / "003_critica.sql").write_text("SELECT geom;")
    monkeypatch.setattr(migrate, "CARPETA", tmp_path)
    with pytest.raises(RuntimeError):
        migrate.aplicar(_Motor(sin_postgis=True))


# ---------------------------------------------------- WebSocket: mismo sitio
def test_origen_del_mismo_sitio_se_acepta_sin_configurar():
    assert mensajeria.origen_permitido("https://movilidad.onrender.com", "movilidad.onrender.com") is True
    assert mensajeria.origen_permitido("https://malo.example", "movilidad.onrender.com") is False
    assert mensajeria.origen_permitido("https://movilidad.onrender.com.malo.example", "movilidad.onrender.com") is False


def test_websocket_mismo_sitio_y_ajeno(client):
    with client.websocket_connect("/api/ws", headers={"origin": "http://testserver", "host": "testserver"}):
        pass
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws", headers={"origin": "https://malo.example"}):
            pass


# ---------------------------------------------------- HSTS y CSP en la aplicación
def test_hsts_solo_cuando_la_conexion_es_https(client):
    sin = client.get("/api/health")
    assert "strict-transport-security" not in sin.headers
    con = client.get("/api/health", headers={"x-forwarded-proto": "https"})
    assert con.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


def test_csp_presente_y_docs_excluidos(client):
    csp = client.get("/api/health", headers={"host": "movilidad.onrender.com"}).headers["content-security-policy"]
    # El service worker pide los mosaicos del mapa con fetch(): deben estar en connect-src
    conectar = [d for d in csp.split(";") if d.strip().startswith("connect-src")][0]
    assert "https://tile.openstreetmap.org" in conectar and "https://api.maptiler.com" in conectar
    assert "default-src 'self'" in csp and "wss://movilidad.onrender.com" in csp and "frame-ancestors 'none'" in csp
    assert "content-security-policy" not in client.get("/docs").headers  # Swagger carga scripts externos


# ---------------------------------------------------- web estática en el mismo servicio
def _app_con_estaticos(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>SPA</html>")
    (tmp_path / "assets" / "app-abc123.js").write_text("console.log(1)")
    (tmp_path / "sw.js").write_text("//sw")
    (tmp_path / "secreto.txt").write_text("no")
    (tmp_path.parent / "fuera.txt").write_text("fuera de la carpeta")
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    import importlib
    import app.main as m
    importlib.reload(m)
    return m


def test_sirve_la_web_y_protege_la_api(tmp_path, monkeypatch):
    m = _app_con_estaticos(tmp_path, monkeypatch)
    try:
        with TestClient(m.app) as c:
            r = c.get("/")
            assert r.status_code == 200 and "SPA" in r.text and r.headers["cache-control"] == "no-cache"
            assert "SPA" in c.get("/info").text                      # ruta de la SPA → index.html
            a = c.get("/assets/app-abc123.js")
            assert a.status_code == 200 and "immutable" in a.headers["cache-control"]
            assert c.get("/sw.js").headers["cache-control"] == "no-cache"
            assert c.get("/assets/no-existe.js").status_code == 404   # un archivo inexistente no devuelve la página
            assert c.get("/api/no-existe").status_code == 404          # la API no cae en el index.html
            assert c.get("/api/health").json()["estado"] == "ok"       # y la API sigue funcionando
            # recorrido de rutas: no puede salir de la carpeta estática
            for intento in ("/../fuera.txt", "/%2e%2e/fuera.txt", "/..%2ffuera.txt"):
                assert "fuera de la carpeta" not in c.get(intento).text
    finally:
        monkeypatch.delenv("STATIC_DIR", raising=False)
        import importlib
        import app.main as m2
        importlib.reload(m2)
