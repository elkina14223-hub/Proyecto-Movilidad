import os
import tempfile

# Base de datos aislada para las pruebas
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["SEED_DEMO_DATA"] = "1"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import ipv as ipvlib  # noqa: E402
from app.main import _hits, app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["registros_trafico"] == 4 * 7 * 24


def test_clasificacion_umbrales():
    assert ipvlib.clasificar(0)["nivel"] == "fluido"
    assert ipvlib.clasificar(33)["nivel"] == "fluido"
    assert ipvlib.clasificar(34)["nivel"] == "moderado"
    assert ipvlib.clasificar(66)["nivel"] == "moderado"
    assert ipvlib.clasificar(67)["nivel"] == "congestionado"
    assert ipvlib.clasificar(100)["nivel"] == "congestionado"


def test_rf01_horas_pico_tarde_entre_semana(client):
    d = client.get("/api/trafico/horas", params={"dia": 1}).json()
    assert len(d["horas"]) == 24
    assert any(16 <= h <= 19 for h in d["horas_pico"]), "debe haber pico en la tarde"
    # La tarde pesa más que el mediodía
    por_hora = {h["hora"]: h["ipv"] for h in d["horas"]}
    assert por_hora[17] > por_hora[12] > por_hora[3]


def test_rf02_slot_y_nivel_en_texto(client):
    d = client.get("/api/trafico/slot", params={"dia": 2, "hora": 17}).json()
    assert len(d["tramos"]) == 4
    assert d["etiqueta"] in {"Fluido", "Moderado", "Congestionado"}
    assert all("etiqueta" in t and "color" in t for t in d["tramos"])


def test_rf03_comparacion_7_dias(client):
    d = client.get("/api/trafico/comparacion").json()["dias"]
    assert len(d) == 7 and all(len(x["ipv_por_hora"]) == 24 for x in d)


def test_rf04_mejores_franjas_son_fluidas(client):
    f = client.get("/api/recomendaciones/franjas", params={"dia": 1}).json()["franjas"]
    assert len(f) == 4
    assert all(x["ipv"] <= 66 for x in f)


def test_rf05_rf06_rutas_y_transporte(client):
    assert len(client.get("/api/rutas").json()) >= 1
    t = client.get("/api/transporte").json()
    assert t and isinstance(t[0]["paraderos"], list)


def test_rf07_trafico_actual_informa_no_disponible(client):
    d = client.get("/api/trafico/actual").json()
    assert d["disponible"] is False
    assert "no está disponible" in d["mensaje"]
    assert "tipico" in d


def test_rf09_ipv_en_rango(client):
    for dia in range(7):
        for hora in (6, 12, 17, 23):
            v = client.get("/api/ipv", params={"dia": dia, "hora": hora}).json()
            assert 0 <= v["ipv_promedio"] <= 100


def test_rf10_pronostico_con_confianza(client):
    p = client.get("/api/pronostico", params={"dia": 1, "hora": 14, "horas": 6}).json()["horas"]
    assert len(p) == 6
    assert all(0 <= x["confianza"] <= 1 for x in p)
    assert p[0]["hora"] == 14 and p[3]["hora"] == 17


def test_rf10_planificador_ahorra_tiempo_en_hora_pico(client):
    p = client.get("/api/planificador", params={"dia": 1, "hora": 17}).json()
    assert p["hora_sugerida"] != 17
    assert p["ahorro_vs_hora_deseada_min"] > 0
    assert p["tiempo_estimado_min"] < p["tiempo_hora_deseada_min"]
    assert "mensaje" in p and p["alternativas"]


def test_rf10_planificador_hora_valle_no_cambia(client):
    p = client.get("/api/planificador", params={"dia": 1, "hora": 10}).json()
    assert p["ahorro_vs_hora_deseada_min"] <= 2


def test_rf08_rf11_reporte_se_valida_con_confirmaciones(client):
    _hits.clear()
    hoy_dia_hora = client.get("/api/trafico/actual").json()
    dia, hora = hoy_dia_hora["dia_semana"], hoy_dia_hora["hora"]
    antes = client.get("/api/trafico/slot", params={"dia": dia, "hora": hora}).json()["tramos"][1]

    r = client.post("/api/reportes", json={"tramo_codigo": "T2", "tipo": "accidente", "comentario": "Choque"},
                    headers={"user-agent": "autor"})
    assert r.status_code == 201
    rep = r.json()
    assert rep["validado"] is False

    # Sin validar no ajusta el IPV
    sin = client.get("/api/trafico/slot", params={"dia": dia, "hora": hora}).json()["tramos"][1]
    assert sin["ipv"] == antes["ipv"] and not sin["ajustado_por_comunidad"]

    # Confirmaciones de otras personas
    for ua in ("a", "b"):
        c = client.post(f"/api/reportes/{rep['id']}/confirmar", headers={"user-agent": ua})
        assert c.status_code == 200
    assert c.json()["validado"] is True

    con = client.get("/api/trafico/slot", params={"dia": dia, "hora": hora}).json()["tramos"][1]
    assert con["ajustado_por_comunidad"] is True
    assert con["ipv"] >= antes["ipv"]


def test_reporte_no_confirma_el_autor_ni_repite(client):
    r = client.post("/api/reportes", json={"tramo_codigo": "T1", "tipo": "obra"}, headers={"user-agent": "x1"}).json()
    assert client.post(f"/api/reportes/{r['id']}/confirmar", headers={"user-agent": "x1"}).status_code == 409
    assert client.post(f"/api/reportes/{r['id']}/confirmar", headers={"user-agent": "y1"}).status_code == 200
    assert client.post(f"/api/reportes/{r['id']}/confirmar", headers={"user-agent": "y1"}).status_code == 409


def test_reporte_validacion_de_entrada(client):
    assert client.post("/api/reportes", json={"tramo_codigo": "T1", "tipo": "invalido"}).status_code == 422
    assert client.post("/api/reportes", json={"tramo_codigo": "ZZ", "tipo": "obra"}).status_code == 404
    assert client.post("/api/reportes", json={"tramo_codigo": "T1", "tipo": "otro", "comentario": "x" * 281}).status_code == 422


def test_limite_de_reportes_por_hora(client):
    _hits.clear()
    codigos = [client.post("/api/reportes", json={"tramo_codigo": "T3", "tipo": "otro"},
                           headers={"user-agent": "spam"}).status_code for _ in range(7)]
    assert codigos[:5] == [201] * 5 and codigos[5] == 429


def test_fuentes_indica_demo_y_explica_ipv(client):
    d = client.get("/api/fuentes").json()
    assert d["es_demostracion"] is True
    assert "0 a 100" in d["ipv_explicacion"]


def test_cabeceras_de_seguridad(client):
    h = client.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
