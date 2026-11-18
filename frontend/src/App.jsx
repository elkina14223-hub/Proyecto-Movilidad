import { useEffect, useState } from 'react'
import Alternativas from './screens/Alternativas.jsx'
import Info from './screens/Info.jsx'
import Inicio from './screens/Inicio.jsx'
import Planificador from './screens/Planificador.jsx'
import Reportar from './screens/Reportar.jsx'
import useEventos, { textoEvento } from './useEventos.js'
import { ahoraBogota } from './util.js'

const SECCIONES = [
  { id: 'inicio', texto: 'Inicio', icono: '◔' },
  { id: 'planificador', texto: 'Salir', icono: '⏱' },
  { id: 'alternativas', texto: 'Rutas', icono: '⇄' },
  { id: 'reportar', texto: 'Reportar', icono: '✎' },
  { id: 'info', texto: 'Info', icono: 'ⓘ' },
]

export default function App() {
  const ahora = ahoraBogota()
  // Enlaces directos: https://dominio/#info abre la sección Info
  const inicial = SECCIONES.some((s) => s.id === window.location.hash.slice(1)) ? window.location.hash.slice(1) : 'inicio'
  const [seccion, setSeccion] = useState(inicial)
  const [dia, setDia] = useState(ahora.dia)
  const [hora, setHora] = useState(ahora.hora)
  const [evento, setEvento] = useState(null)   // último evento en vivo (mensajería sincrónica)
  const [aviso, setAviso] = useState(null)

  const enVivo = useEventos((e) => {
    setEvento({ ...e, n: Date.now() })
    const t = textoEvento(e)
    if (t) setAviso(t)
  })

  useEffect(() => {
    if (!aviso) return undefined
    const id = setTimeout(() => setAviso(null), 6000)
    return () => clearTimeout(id)
  }, [aviso])

  const irA = (s) => { setSeccion(s); window.history.replaceState(null, '', `#${s}`); window.scrollTo({ top: 0 }) }
  const props = { dia, hora, setDia, setHora, irA, evento }

  return (
    <div className="app">
      <a href="#contenido" className="saltar">Saltar al contenido</a>
      <header className="cabecera">
        <span className="marca">Pradilla<em>/Chía</em></span>
        <span className={`en-vivo ${enVivo ? 'si' : 'no'}`} role="status">
          <span aria-hidden="true">{enVivo ? '●' : '○'}</span> {enVivo ? 'En vivo' : 'Sin conexión en vivo'}
        </span>
      </header>
      {aviso && <div className="toast" role="status" aria-live="polite">{aviso}</div>}
      <main id="contenido" tabIndex={-1}>
        {seccion === 'inicio' && <Inicio {...props} />}
        {seccion === 'planificador' && <Planificador {...props} />}
        {seccion === 'alternativas' && <Alternativas />}
        {seccion === 'reportar' && <Reportar evento={evento} />}
        {seccion === 'info' && <Info />}
      </main>
      <nav className="nav" aria-label="Secciones">
        {SECCIONES.map((s) => (
          <button key={s.id} type="button" className={seccion === s.id ? 'activo' : ''}
            aria-current={seccion === s.id ? 'page' : undefined} onClick={() => irA(s.id)}>
            <span aria-hidden="true">{s.icono}</span>{s.texto}
          </button>
        ))}
      </nav>
    </div>
  )
}
