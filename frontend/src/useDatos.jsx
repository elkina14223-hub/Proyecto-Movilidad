import { useCallback, useEffect, useState } from 'react'

/** Carga datos de la API con estado de carga y error (RNF-CON: mensajes claros si falla la fuente). */
export default function useDatos(fn, deps) {
  const [estado, setEstado] = useState({ datos: null, cargando: true, error: null })
  const [version, setVersion] = useState(0)
  const recargar = useCallback(() => setVersion((v) => v + 1), [])

  useEffect(() => {
    let activo = true
    setEstado((s) => ({ ...s, cargando: true, error: null }))
    fn()
      .then((datos) => activo && setEstado({ datos, cargando: false, error: null }))
      .catch((e) => activo && setEstado({ datos: null, cargando: false, error: e.message || 'No se pudo cargar' }))
    return () => { activo = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, version])

  return { ...estado, recargar }
}

export function Estado({ cargando, error, recargar, children }) {
  if (error) {
    return (
      <div className="aviso aviso-error" role="alert">
        No pudimos cargar la información ({error}). Revisa tu conexión.
        {recargar && <button type="button" className="btn-link" onClick={recargar}>Reintentar</button>}
      </div>
    )
  }
  if (cargando) return <div className="cargando" aria-live="polite">Cargando…</div>
  return children
}
