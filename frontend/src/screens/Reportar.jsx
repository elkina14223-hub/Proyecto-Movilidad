import { useState } from 'react'
import { api } from '../api.js'
import useDatos, { Estado } from '../useDatos.jsx'

const TIPOS = { trancon: 'Trancón', accidente: 'Accidente', obra: 'Obra', otro: 'Otro' }

/** RF-08 (reportar sin registro) y RF-11 (validación con confirmaciones de otras personas). */
export default function Reportar({ evento }) {
  const tramos = useDatos(() => api.tramos(), [])
  const reportes = useDatos(() => api.reportes(), [evento?.n])  // se actualiza sola con cada evento en vivo
  const [form, setForm] = useState({ tramo_codigo: 'T2', tipo: 'trancon', comentario: '' })
  const [msg, setMsg] = useState(null)
  const [enviando, setEnviando] = useState(false)

  async function enviar(e) {
    e.preventDefault()
    setEnviando(true); setMsg(null)
    try {
      const rep = await api.crearReporte(form)
      const n = rep.confirmaciones_necesarias
      setMsg({ ok: true, texto: `Gracias. Tu reporte ajustará el índice cuando ${n === 1 ? 'otra persona lo confirme' : `otras ${n} personas lo confirmen`}.` })
      setForm({ ...form, comentario: '' })
      reportes.recargar()
    } catch (err) {
      setMsg({ ok: false, texto: err.message })
    } finally { setEnviando(false) }
  }

  async function confirmar(id) {
    try { await api.confirmar(id); reportes.recargar() }
    catch (err) { setMsg({ ok: false, texto: err.message }) }
  }

  return (
    <>
      <section className="tarjeta">
        <p className="sobre">Comunidad</p>
        <h1>Reportar un incidente</h1>
        <p className="nota">No necesitas registrarte. No guardamos tu ubicación ni tu IP.</p>
        <form onSubmit={enviar} className="form">
          <label>Tramo
            <select value={form.tramo_codigo} onChange={(e) => setForm({ ...form, tramo_codigo: e.target.value })}>
              {(tramos.datos ?? []).map((t) => <option key={t.codigo} value={t.codigo}>{t.nombre}</option>)}
            </select>
          </label>
          <fieldset>
            <legend>¿Qué pasa?</legend>
            <div className="chips">
              {Object.entries(TIPOS).map(([v, t]) => (
                <label key={v} className={`chip ${form.tipo === v ? 'activo' : ''}`}>
                  <input type="radio" name="tipo" value={v} checked={form.tipo === v}
                    onChange={() => setForm({ ...form, tipo: v })} className="solo-lectores" />
                  {t}
                </label>
              ))}
            </div>
          </fieldset>
          <label>Comentario (opcional)
            <textarea maxLength={280} rows={3} value={form.comentario}
              onChange={(e) => setForm({ ...form, comentario: e.target.value })} placeholder="Ej.: carril derecho bloqueado" />
            <small>{form.comentario.length}/280</small>
          </label>
          <button type="submit" className="btn-primario" disabled={enviando}>{enviando ? 'Enviando…' : 'Enviar reporte'}</button>
        </form>
        {msg && <p className={`aviso ${msg.ok ? 'aviso-ok' : 'aviso-error'}`} role="status">{msg.texto}</p>}
      </section>

      <section className="tarjeta">
        <h2>Reportes vigentes</h2>
        <Estado {...reportes}>
          {reportes.datos && (reportes.datos.length === 0
            ? <p className="nota">No hay reportes vigentes.</p>
            : reportes.datos.map((r) => (
              <article key={r.id} className="item">
                <h3>{TIPOS[r.tipo]} · {r.tramo_codigo}
                  <span className={`sello ${r.validado ? 'sello-ok' : ''}`}>{r.validado ? 'Validado' : 'Sin validar'}</span>
                </h3>
                {r.comentario && <p>{r.comentario}</p>}
                <p className="detalle">
                  {r.confirmaciones}/{r.confirmaciones_necesarias} confirmaciones · vence {new Date(r.vigente_hasta).toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit', timeZone: 'America/Bogota' })}
                </p>
                {!r.validado && <button type="button" className="btn-sec" onClick={() => confirmar(r.id)}>Yo también lo veo</button>}
              </article>
            ))
          )}
        </Estado>
        <p className="nota">Solo los reportes validados y vigentes ajustan el índice.</p>
      </section>
    </>
  )
}
