import { ICONO_NIVEL } from '../util.js'

/** Nivel de tráfico en color Y en texto (más un símbolo), para no depender solo del color. */
export default function Nivel({ ipv, nivel, etiqueta, color, grande = false }) {
  return (
    <span className={`nivel ${grande ? 'nivel-grande' : ''}`} style={{ '--c': color }}>
      <span aria-hidden="true">{ICONO_NIVEL[nivel]}</span>
      <strong>{etiqueta}</strong>
      {ipv !== undefined && <span className="nivel-ipv">IPV {ipv}</span>}
    </span>
  )
}
