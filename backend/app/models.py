"""Modelo de datos del histórico de tráfico (KAN-23, RNF-CAP-01).

Entidades: tramos, histórico por hora y día, rutas alternativas,
opciones de transporte y reportes ciudadanos.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Tramo(Base):
    """Segmento de la Avenida Pradilla con su geometría."""

    __tablename__ = "tramos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(120))
    # Lista de [lat, lon] serializada como JSON (en Postgres se complementa con PostGIS, ver db/init.sql)
    geometria: Mapped[str] = mapped_column(Text)
    longitud_m: Mapped[int] = mapped_column(Integer)
    # Tiempo en flujo libre (minutos) para calcular el tiempo ahorrado
    tiempo_libre_min: Mapped[float] = mapped_column(Float)

    historico = relationship("RegistroTrafico", back_populates="tramo", cascade="all, delete-orphan")


class RegistroTrafico(Base):
    """Nivel de congestión (0-100) por tramo, día de la semana y hora."""

    __tablename__ = "registros_trafico"

    id: Mapped[int] = mapped_column(primary_key=True)
    tramo_id: Mapped[int] = mapped_column(ForeignKey("tramos.id"), index=True)
    dia_semana: Mapped[int] = mapped_column(Integer, index=True)  # 0 = lunes ... 6 = domingo
    hora: Mapped[int] = mapped_column(Integer, index=True)  # 0-23
    nivel: Mapped[float] = mapped_column(Float)  # 0-100 (base del IPV)
    muestras: Mapped[int] = mapped_column(Integer, default=1)  # nº de mediciones agregadas
    desviacion: Mapped[float] = mapped_column(Float, default=0.0)  # variabilidad entre mediciones
    fuente: Mapped[str] = mapped_column(String(80))
    periodo: Mapped[str] = mapped_column(String(120))

    tramo = relationship("Tramo", back_populates="historico")


class RutaAlternativa(Base):
    __tablename__ = "rutas_alternativas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    descripcion: Mapped[str] = mapped_column(Text)
    franja_recomendada: Mapped[str] = mapped_column(String(80))
    hora_inicio: Mapped[int] = mapped_column(Integer)
    hora_fin: Mapped[int] = mapped_column(Integer)
    # Minutos adicionales frente a la Av. Pradilla en flujo libre
    extra_min_flujo_libre: Mapped[float] = mapped_column(Float)
    ahorro_hora_pico_min: Mapped[float] = mapped_column(Float)
    geometria: Mapped[str] = mapped_column(Text)


class OpcionTransporte(Base):
    __tablename__ = "opciones_transporte"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120))
    tipo: Mapped[str] = mapped_column(String(40))
    descripcion: Mapped[str] = mapped_column(Text)
    paraderos: Mapped[str] = mapped_column(Text)
    horario: Mapped[str] = mapped_column(String(120))


class ReporteCiudadano(Base):
    """Reporte de la comunidad (RF-08) y su validación (RF-11)."""

    __tablename__ = "reportes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tramo_id: Mapped[int] = mapped_column(ForeignKey("tramos.id"), index=True)
    tipo: Mapped[str] = mapped_column(String(30))  # trancon, accidente, obra, otro
    comentario: Mapped[str] = mapped_column(String(280), default="")
    creado: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    vigente_hasta: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Votos de confirmación de otras personas (validación comunitaria)
    confirmaciones: Mapped[int] = mapped_column(Integer, default=0)
    validado: Mapped[bool] = mapped_column(Boolean, default=False)
    # Huella con sal del cliente para limitar spam; no se guarda la IP (Ley 1581)
    huella: Mapped[str] = mapped_column(String(64), default="")
