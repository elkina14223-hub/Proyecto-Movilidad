import { useMemo } from 'react'
import { api } from '../api.js'
import Nivel from '../components/Nivel.jsx'
import GraficoHoras from '../components/GraficoHoras.jsx'
import Mapa7Dias from '../components/Mapa7Dias.jsx'
import MapaTramos from '../components/MapaTramos.jsx'
import Selector from '../components/Selector.jsx'
import useDatos, { Estado } from '../useDatos.jsx'
import { DIAS, fmtHora } from '../util.js'

export default function Inicio({ dia, hora, setDia, setHora, irA, evento }) {
  // Cuando la comunidad valida un reporte (evento en vivo), se vuelve a pedir el índice
  const vivo = evento?.tipo === 'reporte_validado' ? evento.n : 0
  const tramos = useDatos(() => api.tramos(), [])
  const horas = useDatos(() => api.horas(dia), [dia, vivo])
  const slot = useDatos(() => api.slot(dia, hora), [dia, hora, vivo])
  const actual = useDatos(() => api.actual(), [])
  const franjas = useDatos(() => api.franjas(dia), [dia])
  const comparacion = useDatos(() => api.comparacion(), [])
  const rutas = useDatos(() => api.rutas(), [])

  const niveles = useMemo(() => slot.datos?.tramos ?? [], [slot.datos])

  return (
    <>
      <section className="tarjeta tarjeta-hero">
        <p className="sobre">Avenida Pradilla · Chía</p>
        <h1>¿Cómo está la avenida hoy?</h1>
        <Estado {...actual}>
          {actual.datos && (
            <>
              <div className="hero-nivel">
                <Nivel grande ipv={actual.datos.tipico.ipv_promedio} {...actual.datos.tipico} />
                <span className="hero-hora">típico para {actual.datos.dia.toLowerCase()} {fmtHora(actual.datos.hora)}</span>
              </div>
              {!actual.datos.disponible && <p className="nota">{actual.datos.mensaje}</p>}
            </>
          )}
        </Estado>
        <button type="button" className="btn-primario" onClick={() => irA('planificador')}>
          ¿A qué hora salgo? →
        </button>
      </section>

      <section className="tarjeta">
        <h2>Horas pico del {DIAS[dia].toLowerCase()}</h2>
        <Selector dia={dia} hora={hora} onDia={setDia} onHora={setHora} />
        <Estado {...horas}>
          {horas.datos && <GraficoHoras datos={horas.datos} horaSeleccionada={hora} onSeleccionar={setHora} />}
        </Estado>
      </section>

      <section className="tarjeta">
        <h2>{DIAS[dia]} a las {fmtHora(hora)}</h2>
        <Estado {...slot}>
          {slot.datos && (
            <>
              <Nivel grande ipv={slot.datos.ipv_promedio} {...slot.datos} />
              <MapaTramos tramos={tramos.datos ?? []} niveles={niveles} rutas={rutas.datos ?? []} />
              <ul className="lista-tramos">
                {niveles.map((t) => (
                  <li key={t.tramo_codigo}>
                    <span>{t.tramo}</span>
                    <Nivel ipv={t.ipv} {...t} />
                  </li>
                ))}
              </ul>
              {niveles.some((t) => t.ajustado_por_comunidad) && (
                <p className="nota nota-comunidad">Algunos tramos están ajustados por reportes confirmados de la comunidad.</p>
              )}
            </>
          )}
        </Estado>
      </section>

      <section className="tarjeta">
        <h2>Mejores horas para salir el {DIAS[dia].toLowerCase()}</h2>
        <Estado {...franjas}>
          {franjas.datos && (
            <ul className="franjas">
              {franjas.datos.franjas.map((f) => (
                <li key={f.hora}><button type="button" onClick={() => setHora(f.hora)}>
                  <strong>{fmtHora(f.hora)}</strong><Nivel ipv={f.ipv} {...f} />
                </button></li>
              ))}
            </ul>
          )}
        </Estado>
      </section>

      <section className="tarjeta">
        <h2>Compara los días</h2>
        <Estado {...comparacion}>
          {comparacion.datos && <Mapa7Dias datos={comparacion.datos} diaActivo={dia} onDia={setDia} />}
        </Estado>
      </section>
    </>
  )
}
