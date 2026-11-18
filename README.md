# Movilidad Av. Pradilla (Chía)

MVP web (PWA) para la problemática de congestión de la Avenida Pradilla: muestra las **horas pico**, ofrece **rutas alternativas y transporte**, y su diferencial es el **Índice de Presión Vial (IPV)** y el planificador **«¿A qué hora salgo?»**.
Construido a partir del proyecto Jira KAN (SRS v1.0 → v1.1).

## Estado actual: importante

- **El histórico de tráfico es sintético (datos de demostración).** Las épicas de investigación (KAN-6: KAN-18, KAN-19, KAN-35, KAN-36) siguen «Por hacer». La app lo indica en la pantalla *Info* y en `/api/fuentes`. Cuando tengan mediciones reales: `python -m app.import_csv mediciones.csv` (formato en `backend/app/import_csv.py`) y ponga `SEED_DEMO_DATA=0`.
- Las **geometrías de los tramos** (`backend/app/seed.py`) son **aproximadas**: ajústelas con el trazado real.
- **Rutas alternativas y transporte** son ejemplos plausibles; deben validarse con KAN-20.
- **RF-07 (tráfico actual):** no hay fuente en tiempo real conectada; la app informa «no disponible» y muestra el nivel típico (como permite el criterio de aceptación de KAN-26).
- Las migraciones PostGIS y el `docker-compose` **no pudieron ejecutarse en el entorno donde se construyó** (sin Docker/PostgreSQL). Se probó la API con SQLite (56 pruebas) y el front-end (3 pruebas + build). Tampoco se pudo desplegar en Render (sin cuenta/Docker): pruebe `docker compose up --build` o el *Blueprint* de Render y reporte errores.

## Cómo ejecutarlo

### Desarrollo rápido (sin Docker)
```bash
cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload      # http://localhost:8000/docs
cd frontend && npm install && npm run dev                                          # http://localhost:5173
```
### Con Docker (PostgreSQL + PostGIS, HTTPS)
```bash
cp .env.example .env            # complete POSTGRES_PASSWORD y REPORT_SALT
./scripts/gen-dev-cert.sh       # certificado autofirmado solo para desarrollo
docker compose up --build       # https://localhost:8443  (http://localhost:8080 redirige con 301)
```
Mapa: cree una clave en MapTiler y póngala en `VITE_MAPTILER_KEY`; sin clave usa OpenStreetMap público.

## Publicación (servidor, hosting, dominio y certificado)
- **Render, plan gratuito (elegido):** **[docs/DESPLIEGUE_RENDER.md](docs/DESPLIEGUE_RENDER.md)** (`render.yaml` + `Dockerfile.render`).
- Alternativa con servidor propio (VPS + Let's Encrypt): **[docs/DESPLIEGUE.md](docs/DESPLIEGUE.md)**.

La pantalla *Info → Entorno de publicación* muestra el estado real de servidor, hosting, dominio y certificado (tipo DV/OV/EV, vigencia, TLS), leído del propio servidor (`/api/entorno`).

## Respuestas para el profesor
Vea **[docs/RESPUESTAS_PROFESOR.md](docs/RESPUESTAS_PROFESOR.md)**: servidor, arquitectura, TLS y mensajería sincrónica/asincrónica (WebSocket, Telegram, correo SMTP).

## Cobertura del Jira

| Jira | Requisito | Dónde |
|---|---|---|
| KAN-24 | RF-01 gráfico de horas pico · RF-02 selector día/hora · RF-03 comparación entre días | `GraficoHoras`, `Selector`, `Mapa7Dias`, `/api/trafico/*` |
| KAN-25 | RF-04 mejores franjas · RF-05 rutas alternativas · RF-06 transporte | `Inicio`, `Alternativas`, `/api/recomendaciones/franjas`, `/api/rutas`, `/api/transporte` |
| KAN-26 | RF-07 tráfico actual (o «no disponible») · RF-08 reporte sin registro | `Inicio`, `Reportar` |
| KAN-44 | RF-09 IPV 0–100 (fluido 0–33, moderado 34–66, congestionado 67–100), color + texto | `backend/app/ipv.py`, `Nivel` |
| KAN-45 | RF-10 pronóstico con confianza y planificador (resultado en 1 toque, máx. 3) | `Planificador`, `/api/pronostico`, `/api/planificador` |
| KAN-46 | RF-11 reportes validados (2 confirmaciones), vigentes (60 min) y marcados en la interfaz | `/api/reportes`, `Reportar` |
| KAN-23/41 | Modelo de datos y PostGIS | `models.py`, `backend/db/migrations` |
| KAN-38/40/39/42/43 | Docker, FastAPI, PWA React+Vite+Recharts, Leaflet+MapTiler, CI | `docker-compose.yml`, `backend/`, `frontend/`, `.github/workflows` |
| KAN-27/28 | HTTPS, 301, HSTS, TLS 1.3/1.2 AES-GCM, sin versión de servidor, cabeceras | `frontend/nginx/` |
| KAN-29/49 | Ley 1581 (sin registro, sin IP guardada), fuente/periodo, explicación del IPV, privacidad/términos | `Info`, `/api/fuentes`, `main.py` |
| KAN-30 | Baja latencia / alojamiento en Colombia o CDN | **Pendiente de decisión del equipo** (caché larga de estáticos ya configurada) |
| KAN-31/32/48 | Pruebas en dispositivos, documentación final, disponibilidad/backups | **Pendiente** (pruebas automáticas incluidas; mediciones reales de rendimiento y respaldos de BD no) |

## Cómo se calcula el IPV
`IPV = nivel histórico típico del tramo (día, hora) + ajuste por reportes validados y vigentes (máx. +25)`. El pronóstico usa un modelo estacional simple (misma hora y día de la semana) y la confianza depende del número de muestras y su variabilidad. El planificador evalúa ±3 h alrededor de la hora deseada y estima el tiempo como `tiempo libre × (1 + 2,5 × IPV/100)`. Los parámetros (factor de retraso, ajustes por tipo de reporte) son **supuestos iniciales** en `ipv.py` que deben calibrarse con datos reales.

## Pruebas
`cd backend && pytest` · `cd frontend && npm test && npm run build`
