import { Bar, BarChart, Cell, ResponsiveContainer, XAxis, YAxis, Tooltip } from 'recharts'
import { api } from '../api.js'
import Nivel from '../components/Nivel.jsx'
import Selector from '../components/Selector.jsx'
import useDatos, { Estado } from '../useDatos.jsx'
import { clasificar, DIAS, fmtHora } from '../util.js'

/** RF-10: «¿A qué hora salgo?» — el resultado aparece apenas se abre la pantalla (1 toque desde inicio). */
export default function Planificador({ dia, hora, setDia, setHora }) {
  const plan = useDatos(() => api.planificador(dia, hora), [dia, hora])
  const pron = useDatos(() => api.pronostico(dia, hora), [dia, hora])

  return (
    <>
      <section className="tarjeta">
        <p className="sobre">Planificador de salida</p>
        <h1>¿A qué hora salgo?</h1>
        <p className="nota">Elige el día y la hora en la que querías salir.</p>
        <Selector dia={dia} hora={hora} onDia={setDia} onHora={setHora} />
      </section>

      <Estado {...plan}>
        {plan.datos && (
          <section className="tarjeta tarjeta-resultado" aria-live="polite">
            <p className="resultado-mensaje">{plan.datos.mensaje}</p>
            <div className="metricas">
              <div><span>Sal a las</span><strong>{fmtHora(plan.datos.hora_sugerida)}</strong></div>
              <div><span>Tiempo estimado</span><strong>{plan.datos.tiempo_estimado_min} min</strong></div>
              <div><span>Ahorras</span><strong>{plan.datos.ahorro_vs_hora_deseada_min} min</strong></div>
            </div>
            <p className="detalle">
              Ruta: <strong>{plan.datos.ruta_sugerida}</strong>. Presión a esa hora: <Nivel ipv={plan.datos.ipv_hora_sugerida} {...plan.datos} />
            </p>
            {plan.datos.ahorro_vs_hora_pico_min > 0 && (
              <p className="detalle">
                Frente a la hora pico del {DIAS[dia].toLowerCase()} ({fmtHora(plan.datos.hora_pico)}) ahorras unos {plan.datos.ahorro_vs_hora_pico_min} min.
              </p>
            )}
            <p className="nota">Confianza de la estimación: {Math.round(plan.datos.confianza * 100)} %. Es una estimación basada en el histórico.</p>

            <h2>Tiempo según la hora de salida</h2>
            <div className="grafico" role="img" aria-label="Minutos de viaje según la hora de salida">
              <ResponsiveContainer width="100%" height={170}>
                <BarChart data={plan.datos.alternativas} margin={{ top: 8, right: 4, left: -20, bottom: 0 }}>
                  <XAxis dataKey="hora" tickFormatter={fmtHora} tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} unit=" m" />
                  <Tooltip formatter={(v) => [`${v} min`, 'Viaje']} labelFormatter={fmtHora} />
                  <Bar dataKey="minutos" radius={[3, 3, 0, 0]}>
                    {plan.datos.alternativas.map((a) => (
                      <Cell key={a.hora} fill={clasificar(a.ipv).color}
                        stroke={a.hora === plan.datos.hora_sugerida ? '#0f3d3e' : 'none'} strokeWidth={3} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}
      </Estado>

      <section className="tarjeta">
        <h2>Pronóstico de las próximas horas</h2>
        <Estado {...pron}>
          {pron.datos && (
            <>
              <ul className="pronostico">
                {pron.datos.horas.map((p, i) => (
                  <li key={i}>
                    <strong>{fmtHora(p.hora)}</strong>
                    <Nivel ipv={p.ipv} {...p} />
                    <span className="conf">confianza {Math.round(p.confianza * 100)} %</span>
                  </li>
                ))}
              </ul>
              <p className="nota">Modelo: {pron.datos.modelo}.</p>
            </>
          )}
        </Estado>
      </section>
    </>
  )
}
