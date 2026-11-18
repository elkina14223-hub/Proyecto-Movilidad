import { clasificar, DIAS, DIAS_CORTO, fmtHora } from '../util.js'

/** RF-03: comparación del comportamiento entre los días de la semana (mapa de calor 7 × 17 h). */
export default function Mapa7Dias({ datos, diaActivo, onDia }) {
  const horas = Array.from({ length: 18 }, (_, i) => i + 5)
  return (
    <div>
      <div className="calor" role="table" aria-label="IPV por día y hora">
        <div className="calor-fila calor-cab" role="row">
          <span role="columnheader" />
          {horas.map((h) => <span key={h} role="columnheader">{h % 3 === 0 ? h : ''}</span>)}
        </div>
        {datos.dias.map((d) => (
          <div key={d.dia_semana} className={`calor-fila ${d.dia_semana === diaActivo ? 'activa' : ''}`} role="row">
            <button type="button" className="calor-dia" onClick={() => onDia?.(d.dia_semana)} aria-label={`Ver ${DIAS[d.dia_semana]}`}>
              {DIAS_CORTO[d.dia_semana]}
            </button>
            {horas.map((h) => {
              const v = d.ipv_por_hora[h]
              const c = clasificar(v)
              return (
                <span key={h} role="cell" className="calor-celda" style={{ background: c.color, opacity: 0.35 + v / 160 }}
                  title={`${DIAS[d.dia_semana]} ${fmtHora(h)}: ${c.etiqueta} (IPV ${v})`} />
              )
            })}
          </div>
        ))}
      </div>
      <ul className="leyenda">
        <li><i style={{ background: '#2e8540' }} /> Fluido 0–33</li>
        <li><i style={{ background: '#c98f00' }} /> Moderado 34–66</li>
        <li><i style={{ background: '#c0392b' }} /> Congestionado 67–100</li>
      </ul>
      <p className="nota">
        {datos.dias.map((d) => `${DIAS_CORTO[d.dia_semana]}: pico ${fmtHora(d.hora_pico)}`).join(' · ')}
      </p>
    </div>
  )
}
