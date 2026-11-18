// Cliente de la API. En desarrollo Vite redirige /api; en producción lo hace nginx.
async function pedir(ruta, opciones) {
  const r = await fetch(`/api${ruta}`, opciones)
  if (!r.ok) {
    let detalle = ''
    try { detalle = (await r.json()).detail } catch { /* sin cuerpo JSON */ }
    const err = new Error(typeof detalle === 'string' && detalle ? detalle : `Error ${r.status}`)
    err.status = r.status
    throw err
  }
  return r.json()
}

const q = (o) => new URLSearchParams(o).toString()

export const api = {
  tramos: () => pedir('/tramos'),
  horas: (dia) => pedir(`/trafico/horas?${q({ dia })}`),
  slot: (dia, hora) => pedir(`/trafico/slot?${q({ dia, hora })}`),
  comparacion: () => pedir('/trafico/comparacion'),
  actual: () => pedir('/trafico/actual'),
  franjas: (dia) => pedir(`/recomendaciones/franjas?${q({ dia })}`),
  rutas: () => pedir('/rutas'),
  transporte: () => pedir('/transporte'),
  pronostico: (dia, hora) => pedir(`/pronostico?${q({ dia, hora, horas: 6 })}`),
  planificador: (dia, hora) => pedir(`/planificador?${q({ dia, hora })}`),
  fuentes: () => pedir('/fuentes'),
  entorno: () => pedir('/entorno'),
  reportes: () => pedir('/reportes'),
  crearReporte: (datos) =>
    pedir('/reportes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(datos) }),
  confirmar: (id) => pedir(`/reportes/${id}/confirmar`, { method: 'POST' }),
}
