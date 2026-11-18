"""Datos de ejemplo (KAN-41: "Datos de ejemplo cargados para probar la API y los gráficos").

IMPORTANTE: el histórico generado aquí es SINTÉTICO. Sirve para desarrollo y demostración
hasta que el equipo termine la recolección de KAN-18/KAN-19/KAN-35/KAN-36. Para reemplazarlo,
cargue mediciones reales con `python -m app.import_csv datos.csv` (ver README).
Las geometrías de los tramos son aproximadas y deben ajustarse con el trazado real.
"""
import json
import math
import random

from sqlalchemy.orm import Session

from . import models

FUENTE_EJEMPLO = "Datos de ejemplo (sintéticos)"
PERIODO_EJEMPLO = "Simulación - pendiente de mediciones propias"

# Tramos aproximados de la Av. Pradilla (Chía). Ajustar con el trazado real.
TRAMOS = [
    ("T1", "Glorieta Variante - Calle 15", [[4.8745, -74.0412], [4.8718, -74.0431], [4.8692, -74.0452]], 650, 2.0),
    ("T2", "Calle 15 - Centro Comercial", [[4.8692, -74.0452], [4.8664, -74.0478], [4.8638, -74.0503]], 720, 2.2),
    ("T3", "Centro Comercial - Parque principal", [[4.8638, -74.0503], [4.8612, -74.0531], [4.8590, -74.0562]], 680, 2.1),
    ("T4", "Parque principal - Salida a Cajicá", [[4.8590, -74.0562], [4.8560, -74.0588], [4.8531, -74.0617]], 700, 2.3),
]

RUTAS = [
    {
        "nombre": "Ruta por la Carrera 7 (parte baja)",
        "descripcion": "Paralela a la avenida; menos semáforos pero con tramos angostos.",
        "franja_recomendada": "Tardes entre semana (16:00-19:00)",
        "hora_inicio": 16, "hora_fin": 19,
        "extra_min_flujo_libre": 3.0, "ahorro_hora_pico_min": 6.0,
        "geometria": [[4.8740, -74.0440], [4.8660, -74.0510], [4.8540, -74.0640]],
    },
    {
        "nombre": "Ruta por la Variante (circunvalar)",
        "descripcion": "Evita el centro; recomendable cuando el IPV supera 66 en los tramos centrales.",
        "franja_recomendada": "Mañanas entre semana (6:00-9:00)",
        "hora_inicio": 6, "hora_fin": 9,
        "extra_min_flujo_libre": 4.5, "ahorro_hora_pico_min": 7.0,
        "geometria": [[4.8760, -74.0390], [4.8700, -74.0560], [4.8520, -74.0660]],
    },
]

TRANSPORTE = [
    {
        "nombre": "Buses intermunicipales Chía - Bogotá",
        "tipo": "Bus",
        "descripcion": "Servicio frecuente hacia el norte de Bogotá por la Autopista Norte.",
        "paraderos": "Parque principal; Centro Comercial; Glorieta Variante",
        "horario": "5:00 - 21:30 (verificar con la empresa)",
    },
    {
        "nombre": "Rutas urbanas de Chía",
        "tipo": "Buseta",
        "descripcion": "Conectan veredas y barrios con el centro y la avenida.",
        "paraderos": "Paraderos sobre la Av. Pradilla",
        "horario": "5:30 - 20:00 (verificar con la empresa)",
    },
    {
        "nombre": "Bicicleta / ciclorruta",
        "tipo": "Bicicleta",
        "descripcion": "Opción para trayectos cortos cuando la avenida está congestionada.",
        "paraderos": "Acceso por el parque principal",
        "horario": "Todo el día (preferir luz diurna)",
    },
]


def _perfil_hora(dia: int, hora: int) -> float:
    """Perfil base 0-100: pico de mañana y, sobre todo, pico de tarde (según el Jira)."""
    manana = 55 * math.exp(-((hora - 7.0) ** 2) / 2.2)
    tarde = 85 * math.exp(-((hora - 17.5) ** 2) / 3.2)
    mediodia = 28 * math.exp(-((hora - 12.5) ** 2) / 6.0)
    base = 8 + manana + tarde + mediodia
    if dia == 4:  # viernes: tarde más cargada
        base += 8 * math.exp(-((hora - 17.0) ** 2) / 4.0)
    if dia == 5:  # sábado: pico de compras al mediodía
        base = 10 + 45 * math.exp(-((hora - 13.0) ** 2) / 8.0) + 25 * math.exp(-((hora - 18.0) ** 2) / 5.0)
    if dia == 6:  # domingo: regreso por la tarde
        base = 8 + 30 * math.exp(-((hora - 16.5) ** 2) / 6.0)
    if hora < 5 or hora > 22:
        base *= 0.25
    return base


def seed(db: Session, semilla: int = 42) -> None:
    if db.query(models.Tramo).count() > 0:
        return
    rng = random.Random(semilla)

    tramos = []
    for codigo, nombre, geo, largo, libre in TRAMOS:
        t = models.Tramo(codigo=codigo, nombre=nombre, geometria=json.dumps(geo),
                         longitud_m=largo, tiempo_libre_min=libre)
        db.add(t)
        tramos.append(t)
    db.flush()

    # Los tramos centrales (T2, T3) concentran más presión
    factor_tramo = {"T1": 0.85, "T2": 1.0, "T3": 1.1, "T4": 0.95}
    for t in tramos:
        for dia in range(7):
            for hora in range(24):
                base = _perfil_hora(dia, hora) * factor_tramo[t.codigo]
                nivel = max(0.0, min(100.0, base + rng.gauss(0, 3)))
                db.add(models.RegistroTrafico(
                    tramo_id=t.id, dia_semana=dia, hora=hora, nivel=round(nivel, 1),
                    muestras=rng.randint(4, 10), desviacion=round(abs(rng.gauss(6, 2)), 1),
                    fuente=FUENTE_EJEMPLO, periodo=PERIODO_EJEMPLO,
                ))

    for r in RUTAS:
        db.add(models.RutaAlternativa(**{**r, "geometria": json.dumps(r["geometria"])}))
    for o in TRANSPORTE:
        db.add(models.OpcionTransporte(**o))
    db.commit()
