import { api } from '../api.js'
import MapaTramos from '../components/MapaTramos.jsx'
import useDatos, { Estado } from '../useDatos.jsx'
import { fmtHora } from '../util.js'

/** RF-05 (rutas alternativas) y RF-06 (opciones de transporte). */
export default function Alternativas() {
  const rutas = useDatos(() => api.rutas(), [])
  const transporte = useDatos(() => api.transporte(), [])
  const tramos = useDatos(() => api.tramos(), [])

  return (
    <>
      <section className="tarjeta">
        <p className="sobre">Alternativas</p>
        <h1>Rutas y transporte</h1>
        <Estado {...rutas}>
          {rutas.datos && <MapaTramos tramos={tramos.datos ?? []} niveles={[]} rutas={rutas.datos} />}
        </Estado>
        <p className="nota">Línea punteada: rutas alternativas. Línea gris: la Avenida Pradilla.</p>
      </section>

      <section className="tarjeta">
        <h2>Rutas alternativas</h2>
        <Estado {...rutas}>
          {rutas.datos && rutas.datos.map((r) => (
            <article key={r.id} className="item">
              <h3>{r.nombre}</h3>
              <p>{r.descripcion}</p>
              <p className="detalle">
                Conviene entre <strong>{fmtHora(r.hora_inicio)} y {fmtHora(r.hora_fin)}</strong> · {r.franja_recomendada}.
              </p>
              <p className="detalle">
                En hora pico puedes ahorrar ~{r.ahorro_hora_pico_min} min; sin tráfico demora ~{r.extra_min_flujo_libre} min más.
              </p>
            </article>
          ))}
        </Estado>
      </section>

      <section className="tarjeta">
        <h2>Opciones de transporte de la zona</h2>
        <Estado {...transporte}>
          {transporte.datos && transporte.datos.map((o) => (
            <article key={o.id} className="item">
              <h3>{o.nombre} <small>{o.tipo}</small></h3>
              <p>{o.descripcion}</p>
              <p className="detalle"><strong>Paraderos:</strong> {o.paraderos.join(' · ')}</p>
              <p className="detalle"><strong>Horario:</strong> {o.horario}</p>
            </article>
          ))}
        </Estado>
        <p className="nota">Verifica horarios y rutas con las empresas: pueden cambiar.</p>
      </section>
    </>
  )
}
