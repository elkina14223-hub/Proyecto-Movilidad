"""Conexión a la base de datos (KAN-40, KAN-41).

En producción se usa PostgreSQL + PostGIS (variable DATABASE_URL).
Para desarrollo rápido y pruebas se usa SQLite si no hay DATABASE_URL.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

def normalizar_url(url: str) -> str:
    """Render (y otros) entregan postgres:// o postgresql://; SQLAlchemy necesita indicar el driver psycopg."""
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


DATABASE_URL = normalizar_url(os.getenv("DATABASE_URL", "sqlite:///./pradilla.db"))

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
