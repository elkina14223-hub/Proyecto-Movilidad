import os
import tempfile
from datetime import datetime, timedelta, timezone

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/entorno.db"

import pytest  # noqa: E402
from cryptography import x509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from cryptography.x509.oid import NameOID  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import entorno  # noqa: E402
from app.main import app  # noqa: E402


def _crear_cert(ruta, dominio, dias=80, politica=None, autofirmado=False, emisor="Let's Encrypt"):
    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    sujeto = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, dominio)])
    emi = sujeto if autofirmado else x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, emisor), x509.NameAttribute(NameOID.COMMON_NAME, "R11")])
    ahora = datetime.now(timezone.utc)
    b = (x509.CertificateBuilder().subject_name(sujeto).issuer_name(emi).public_key(clave.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(ahora - timedelta(days=10))
         .not_valid_after(ahora + timedelta(days=dias))
         .add_extension(x509.SubjectAlternativeName([x509.DNSName(dominio)]), critical=False))
    if politica:
        b = b.add_extension(x509.CertificatePolicies([x509.PolicyInformation(x509.ObjectIdentifier(politica), None)]), critical=False)
    cert = b.sign(clave, hashes.SHA256())
    with open(ruta, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_certificado_de_dominio_vigente(client, monkeypatch, tmp_path):
    ruta = tmp_path / "c.pem"
    _crear_cert(ruta, "movilidad.ejemplo.co", dias=80, politica="2.23.140.1.2.1")
    monkeypatch.setenv("CERT_FILE", str(ruta))
    monkeypatch.setenv("HOSTING_PROVIDER", "Proveedor de prueba")
    monkeypatch.setenv("HOSTING_REGION", "Bogotá, CO")
    d = client.get("/api/entorno", headers={"host": "movilidad.ejemplo.co", "x-forwarded-proto": "https",
                                            "x-tls-protocol": "TLSv1.3", "x-tls-cipher": "TLS_AES_256_GCM_SHA384"}).json()
    c = d["certificado"]
    assert c["disponible"] and c["estado"] == "vigente"
    assert c["tipo"]["codigo"] == "dominio"
    assert c["emisor"] == "Let's Encrypt"
    assert 70 <= c["dias_restantes"] <= 80
    assert d["dominio"]["estado"] == "operando" and d["dominio"]["certificado_cubre_dominio"] is True
    assert d["hosting"]["proveedor"] == "Proveedor de prueba" and d["hosting"]["configurado"] is True
    assert d["servidor"]["estado"] == "operando"
    assert d["tls"]["https_activo"] and d["tls"]["protocolo"] == "TLSv1.3"


def test_tipos_organizacional_y_extendido(tmp_path):
    for oid, esperado in (("2.23.140.1.2.2", "organizacional"), ("2.23.140.1.1", "extendido")):
        ruta = tmp_path / f"{esperado}.pem"
        _crear_cert(ruta, "a.co", dias=360, politica=oid)
        assert entorno.leer_certificado(str(ruta))["tipo"]["codigo"] == esperado


def test_autofirmado_no_es_confiable(tmp_path):
    ruta = tmp_path / "s.pem"
    _crear_cert(ruta, "localhost", autofirmado=True)
    c = entorno.leer_certificado(str(ruta))
    assert c["estado"] == "no_confiable" and c["tipo"]["codigo"] == "autofirmado"


def test_por_vencer(tmp_path):
    ruta = tmp_path / "v.pem"
    _crear_cert(ruta, "a.co", dias=5, politica="2.23.140.1.2.1")
    assert entorno.leer_certificado(str(ruta))["estado"] == "por_vencer"


def test_sin_certificado_o_ilegible(tmp_path):
    assert entorno.leer_certificado(str(tmp_path / "no.pem"))["disponible"] is False
    malo = tmp_path / "malo.pem"
    malo.write_text("no es un certificado")
    assert entorno.leer_certificado(str(malo))["disponible"] is False


def test_localhost_no_cuenta_como_dominio_publico(client, monkeypatch):
    monkeypatch.setenv("CERT_FILE", "/no/existe.pem")
    monkeypatch.delenv("HOSTING_PROVIDER", raising=False)
    d = client.get("/api/entorno", headers={"host": "localhost:8443"}).json()
    assert d["dominio"]["estado"] == "local" and d["dominio"]["es_dominio_publico"] is False
    assert d["hosting"]["configurado"] is False
    assert d["certificado"]["disponible"] is False


def test_no_expone_clave_privada(client, monkeypatch, tmp_path):
    ruta = tmp_path / "c.pem"
    _crear_cert(ruta, "a.co", politica="2.23.140.1.2.1")
    monkeypatch.setenv("CERT_FILE", str(ruta))
    txt = client.get("/api/entorno", headers={"host": "a.co"}).text
    assert "PRIVATE KEY" not in txt
