"""Migraciones SQL simples (solo PostgreSQL). Cada archivo de db/migrations se aplica una vez.

Las migraciones de PostGIS son OPCIONALES: si el proveedor de la base de datos no ofrece la
extensión (p. ej. algunos planes gratuitos), la aplicación sigue funcionando porque la geometría
de los tramos también se guarda como JSON y el mapa la usa desde ahí.
"""
import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

log = logging.getLogger("migrate")

CARPETA = Path(__file__).resolve().parent.parent / "db" / "migrations"
OPCIONALES = {"001_postgis.sql", "002_geom_tramos.sql"}


def aplicar(engine: Engine) -> list[str]:
    if engine.dialect.name != "postgresql":
        return []
    aplicadas: list[str] = []
    with engine.begin() as con:
        con.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (nombre text PRIMARY KEY, aplicada timestamptz DEFAULT now())"))
        hechas = {r[0] for r in con.execute(text("SELECT nombre FROM schema_migrations"))}

    for archivo in sorted(CARPETA.glob("*.sql")):
        if archivo.name in hechas:
            continue
        try:
            # Una transacción por archivo: si falla una opcional no arrastra a las demás
            with engine.begin() as con:
                # exec_driver_sql evita que SQLAlchemy interprete ':' y '%' dentro del SQL
                con.exec_driver_sql(archivo.read_text(encoding="utf-8"))
                con.execute(text("INSERT INTO schema_migrations (nombre) VALUES (:n)"), {"n": archivo.name})
            aplicadas.append(archivo.name)
        except Exception as e:
            if archivo.name in OPCIONALES:
                log.warning("Migración opcional omitida (%s): %s", archivo.name, type(e).__name__)
                continue
            raise
    return aplicadas
