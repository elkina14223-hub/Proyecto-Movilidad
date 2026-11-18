import { useEffect, useRef, useState } from 'react'

/**
 * Mensajería sincrónica: se conecta por WebSocket (wss:// bajo HTTPS) y avisa de cada evento en vivo.
 * Se reconecta sola con espera creciente si se cae la conexión. Devuelve si está conectado.
 */
export default function useEventos(onEvento) {
  const [conectado, setConectado] = useState(false)
  const cb = useRef(onEvento)
  cb.current = onEvento

  useEffect(() => {
    let ws = null
    let cerrado = false
    let intento = 0
    let temporizador = null

    const abrir = () => {
      const protocolo = window.location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${protocolo}://${window.location.host}/api/ws`)
      ws.onopen = () => { intento = 0; setConectado(true) }
      ws.onmessage = (m) => {
        try { cb.current(JSON.parse(m.data)) } catch { /* mensaje inválido: se ignora */ }
      }
      ws.onclose = () => {
        setConectado(false)
        if (!cerrado) temporizador = setTimeout(abrir, Math.min(30000, 1000 * 2 ** intento++))
      }
      ws.onerror = () => ws.close()
    }

    abrir()
    return () => { cerrado = true; clearTimeout(temporizador); ws?.close() }
  }, [])

  return conectado
}

const TIPOS = { trancon: 'Trancón', accidente: 'Accidente', obra: 'Obra', otro: 'Incidente' }

/** Texto corto para mostrar al usuario según el evento recibido. */
export function textoEvento(e) {
  const t = TIPOS[e.reporte_tipo] ?? 'Incidente'
  if (e.tipo === 'reporte_nuevo') return `Nuevo reporte: ${t} en ${e.tramo_codigo}`
  if (e.tipo === 'reporte_validado') return `${t} validado en ${e.tramo_codigo}: el índice se ajustó`
  if (e.tipo === 'reporte_confirmado') return `Reporte de ${t} en ${e.tramo_codigo} recibió una confirmación`
  return null
}
