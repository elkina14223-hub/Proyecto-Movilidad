import os
import socket
import ssl
import tempfile
import threading
from datetime import datetime, timedelta, timezone

_tmp = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/remoto.db")

import pytest  # noqa: E402
from cryptography import x509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from cryptography.x509.oid import NameOID  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import entorno  # noqa: E402
from app.main import app  # noqa: E402


def _pem(obj):
    return obj.public_bytes(serialization.Encoding.PEM)


@pytest.fixture(scope="module")
def servidor_tls(tmp_path_factory):
    """Servidor TLS local con una CA propia: permite probar la consulta real sin salir a Internet."""
    d = tmp_path_factory.mktemp("tls")
    ahora = datetime.now(timezone.utc)
    ca_k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_n = x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "CA de Prueba"), x509.NameAttribute(NameOID.COMMON_NAME, "CA Prueba")])
    ca = (x509.CertificateBuilder().subject_name(ca_n).issuer_name(ca_n).public_key(ca_k.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(ahora - timedelta(days=1))
          .not_valid_after(ahora + timedelta(days=365))
          .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
          .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_k.public_key()), critical=False)  # Python 3.13 verifica en modo estricto
          .add_extension(x509.KeyUsage(digital_signature=True, key_cert_sign=True, crl_sign=True, content_commitment=False,
                                       key_encipherment=False, data_encipherment=False, key_agreement=False,
                                       encipher_only=False, decipher_only=False), critical=True)
          .sign(ca_k, hashes.SHA256()))
    hoja_k = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    hoja = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
            .issuer_name(ca_n).public_key(hoja_k.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(ahora - timedelta(days=5)).not_valid_after(ahora + timedelta(days=60))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("localhost")]), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(hoja_k.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_k.public_key()), critical=False)
            .add_extension(x509.CertificatePolicies([x509.PolicyInformation(x509.ObjectIdentifier("2.23.140.1.2.1"), None)]), critical=False)
            .sign(ca_k, hashes.SHA256()))
    (d / "ca.pem").write_bytes(_pem(ca))
    (d / "hoja.pem").write_bytes(_pem(hoja))
    (d / "hoja.key").write_bytes(hoja_k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(str(d / "hoja.pem"), str(d / "hoja.key"))
    srv = socket.create_server(("127.0.0.1", 0))
    srv.settimeout(0.3)
    estado = {"conexiones": 0, "activo": True}

    def bucle():
        while estado["activo"]:
            try:
                c, _ = srv.accept()
            except (socket.timeout, OSError):
                continue
            try:
                with ctx.wrap_socket(c, server_side=True):
                    estado["conexiones"] += 1
            except Exception:
                pass

    hilo = threading.Thread(target=bucle, daemon=True)
    hilo.start()
    yield {"puerto": srv.getsockname()[1], "ca": str(d / "ca.pem"), "estado": estado, "hoja_der": hoja.public_bytes(serialization.Encoding.DER)}
    estado["activo"] = False
    srv.close()


@pytest.fixture(autouse=True)
def limpiar_cache():
    entorno._cache_remoto.clear()
    yield
    entorno._cache_remoto.clear()


def test_lee_certificado_protocolo_y_cifrado_reales(servidor_tls):
    r = entorno.consultar_tls_remoto("localhost", servidor_tls["puerto"], cafile=servidor_tls["ca"])
    assert r is not None and r["protocolo"] in ("TLSv1.2", "TLSv1.3") and r["cifrado"]
    info = entorno.interpretar(x509.load_der_x509_certificate(r["der"]))
    assert info["estado"] == "vigente" and info["tipo"]["codigo"] == "dominio"
    assert info["emisor"] == "CA de Prueba" and info["dominios"] == ["localhost"]


def test_no_acepta_una_cadena_que_no_es_de_confianza(servidor_tls):
    # Sin la CA de prueba en el almacén de confianza, la verificación falla y no se muestra como válido
    assert entorno.consultar_tls_remoto("localhost", servidor_tls["puerto"]) is None


def test_resultado_en_cache_no_repite_la_conexion(servidor_tls):
    entorno.consultar_tls_remoto("localhost", servidor_tls["puerto"], cafile=servidor_tls["ca"])
    antes = servidor_tls["estado"]["conexiones"]
    for _ in range(5):
        entorno.consultar_tls_remoto("localhost", servidor_tls["puerto"], cafile=servidor_tls["ca"])
    assert servidor_tls["estado"]["conexiones"] == antes


def test_fallo_de_conexion_devuelve_none_y_se_recuerda():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); puerto = s.getsockname()[1]; s.close()  # puerto cerrado
    assert entorno.consultar_tls_remoto("127.0.0.1", puerto) is None
    assert (("127.0.0.1", puerto)) in entorno._cache_remoto


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_entorno_usa_el_certificado_del_dominio_publico(client, monkeypatch, servidor_tls):
    monkeypatch.setenv("CERT_FILE", "/no/existe.pem")
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "movilidad.onrender.com")
    monkeypatch.setenv("TLS_GESTIONADO_POR", "Render")
    monkeypatch.setattr(entorno, "consultar_tls_remoto",
                        lambda h, p=443, cafile=None: {"der": servidor_tls["hoja_der"], "protocolo": "TLSv1.3", "cifrado": "TLS_AES_256_GCM_SHA384"})
    d = client.get("/api/entorno", headers={"host": "localhost", "x-forwarded-proto": "https"}).json()
    c = d["certificado"]
    assert c["disponible"] and c["estado"] == "vigente" and c["gestionado_por"] == "Render"
    assert "movilidad.onrender.com" in c["origen"]
    assert d["tls"]["protocolo"] == "TLSv1.3" and d["tls"]["cifrado"] == "TLS_AES_256_GCM_SHA384" and d["tls"]["https_activo"]


def test_el_host_de_la_peticion_nunca_decide_a_quien_se_conecta(client, monkeypatch):
    """Anti-SSRF: un Host malicioso no debe provocar conexiones salientes."""
    monkeypatch.setenv("CERT_FILE", "/no/existe.pem")
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)
    monkeypatch.delenv("CERT_REMOTE_HOST", raising=False)
    llamadas = []
    monkeypatch.setattr(entorno, "consultar_tls_remoto", lambda *a, **k: llamadas.append(a))
    client.get("/api/entorno", headers={"host": "interno.evil.example", "x-forwarded-host": "169.254.169.254"})
    assert llamadas == []


def test_sin_poder_consultar_explica_que_lo_gestiona_la_plataforma(client, monkeypatch):
    monkeypatch.setenv("CERT_FILE", "/no/existe.pem")
    monkeypatch.setenv("CERT_REMOTE_HOST", "dominio.ejemplo.co")
    monkeypatch.setenv("TLS_GESTIONADO_POR", "Render")
    monkeypatch.setattr(entorno, "consultar_tls_remoto", lambda *a, **k: None)
    c = client.get("/api/entorno").json()["certificado"]
    assert c["disponible"] is False and "Render" in c["motivo"] and c["gestionado_por"] == "Render"


def test_servidor_web_describe_la_plataforma(client, monkeypatch):
    monkeypatch.setenv("TLS_GESTIONADO_POR", "Render")
    assert "Render" in client.get("/api/entorno").json()["servidor"]["servidor_web"]
    monkeypatch.delenv("TLS_GESTIONADO_POR")
    assert "sin nginx" in client.get("/api/entorno").json()["servidor"]["servidor_web"]
    assert "nginx (versión oculta)" == client.get("/api/entorno", headers={"x-tls-protocol": "TLSv1.3"}).json()["servidor"]["servidor_web"]
