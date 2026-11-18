import { Bar, BarChart, Cell, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtHora } from '../util.js'

/** RF-01: IPV por hora del día con las horas pico marcadas. */
export default function GraficoHoras({ datos, horaSeleccionada, onSeleccionar }) {
  const horas = datos.horas.filter((h) => h.hora >= 5 && h.hora <= 22)
  return (
    <div>
      <div className="grafico" role="img"
        aria-label={`Gráfico de IPV por hora. Horas pico: ${datos.horas_pico.length ? datos.horas_pico.map(fmtHora).join(', ') : 'ninguna'}.`}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={horas} margin={{ top: 8, right: 4, left: -20, bottom: 0 }}
            onClick={(e) => e?.activePayload && onSeleccionar?.(e.activePayload[0].payload.hora)}>
            <CartesianGrid vertical={false} stroke="#d8d0bf" />
            <XAxis dataKey="hora" tickFormatter={(h) => (h % 2 ? '' : h)} tick={{ fontSize: 12 }} />
            <YAxis domain={[0, 100]} ticks={[0, 33, 66, 100]} tick={{ fontSize: 12 }} />
            <ReferenceLine y={67} stroke="#c0392b" strokeDasharray="4 4" label={{ value: 'Pico', fontSize: 11, fill: '#c0392b', position: 'insideTopRight' }} />
            <Tooltip formatter={(v, _n, p) => [`${v} · ${p.payload.etiqueta}`, 'IPV']} labelFormatter={fmtHora} />
            <Bar dataKey="ipv" radius={[3, 3, 0, 0]}>
              {horas.map((h) => (
                <Cell key={h.hora} fill={h.color} stroke={h.hora === horaSeleccionada ? '#0f3d3e' : 'none'} strokeWidth={3} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="nota">
        {datos.horas_pico.length
          ? <>Horas pico: <strong>{datos.horas_pico.map(fmtHora).join(' · ')}</strong></>
          : 'Este día no se espera congestión fuerte.'}
      </p>
      <details className="tabla-alt">
        <summary>Ver como tabla</summary>
        <table>
          <thead><tr><th>Hora</th><th>IPV</th><th>Nivel</th></tr></thead>
          <tbody>{horas.map((h) => <tr key={h.hora}><td>{fmtHora(h.hora)}</td><td>{h.ipv}</td><td>{h.etiqueta}{h.pico ? ' (pico)' : ''}</td></tr>)}</tbody>
        </table>
      </details>
    </div>
  )
}
