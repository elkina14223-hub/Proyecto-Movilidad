"""Importa mediciones reales (KAN-18/KAN-19) y reemplaza el histórico de ejemplo.

Formato del CSV (con encabezado):
    tramo,dia_semana,hora,nivel,muestras,desviacion,fuente,periodo
    T1,0,17,82,6,5.1,Mediciones propias,Nov 2026

- tramo: código del tramo (T1..T4)
- dia_semana: 0 = lunes ... 6 = domingo
- hora: 0-23
- nivel: 0-100 (0 = vía libre, 100 = detenido)

Uso:  python -m app.import_csv mediciones.csv
"""
import csv
import sys

from . import models
from .database import Base, SessionLocal, engine


def importar(ruta: str) -> int:
    Base.metadata.create_all(bind=engine)
    n = 0
    with SessionLocal() as db, open(ruta, newline="", encoding="utf-8") as fh:
        tramos = {t.codigo: t for t in db.query(models.Tramo)}
        if not tramos:
            raise SystemExit("No hay tramos. Inicie la API una vez para crearlos (SEED_DEMO_DATA=1).")
        filas = list(csv.DictReader(fh))
        # Reemplaza solo el histórico sintético de los tramos presentes en el CSV
        codigos = {f["tramo"] for f in filas}
        for c in codigos:
            if c not in tramos:
                raise SystemExit(f"Tramo desconocido: {c}")
            db.query(models.RegistroTrafico).filter_by(tramo_id=tramos[c].id).delete()
        for f in filas:
            nivel = float(f["nivel"])
            dia, hora = int(f["dia_semana"]), int(f["hora"])
            if not (0 <= nivel <= 100 and 0 <= dia <= 6 and 0 <= hora <= 23):
                raise SystemExit(f"Fila fuera de rango: {f}")
            db.add(models.RegistroTrafico(
                tramo_id=tramos[f["tramo"]].id, dia_semana=dia, hora=hora, nivel=nivel,
                muestras=int(f.get("muestras") or 1), desviacion=float(f.get("desviacion") or 0),
                fuente=f.get("fuente") or "Mediciones propias", periodo=f.get("periodo") or "",
            ))
            n += 1
        db.commit()
    return n


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    print(f"{importar(sys.argv[1])} registros importados")
