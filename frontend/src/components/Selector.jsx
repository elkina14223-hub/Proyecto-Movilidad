import { DIAS, DIAS_CORTO, fmtHora } from '../util.js'

/** RF-02: selector de día y franja. */
export default function Selector({ dia, hora, onDia, onHora, mostrarHora = true }) {
  return (
    <div className="selector">
      <div className="chips" role="radiogroup" aria-label="Día de la semana">
        {DIAS_CORTO.map((d, i) => (
          <button key={d} type="button" role="radio" aria-checked={dia === i} aria-label={DIAS[i]}
            className={`chip ${dia === i ? 'activo' : ''}`} onClick={() => onDia(i)}>{d}</button>
        ))}
      </div>
      {mostrarHora && (
        <label className="hora">
          <span>Hora</span>
          <input type="range" min="0" max="23" value={hora} onChange={(e) => onHora(Number(e.target.value))} />
          <output>{fmtHora(hora)}</output>
        </label>
      )}
    </div>
  )
}
