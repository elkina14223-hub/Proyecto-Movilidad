import { useEffect, useRef } from 'react'
import L from 'leaflet'

const CLAVE = import.meta.env.VITE_MAPTILER_KEY
const CENTRO = [4.8638, -74.0503]

// Mapa base de OpenStreetMap servido por MapTiler (KAN-42). Sin clave se usa el servidor público de OSM.
const TILES = CLAVE
  ? `https://api.maptiler.com/maps/openstreetmap/{z}/{x}/{y}.jpg?key=${CLAVE}`
  : 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const ATRIBUCION = CLAVE
  ? '&copy; <a href="https://www.maptiler.com/copyright/">MapTiler</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

export default function MapaTramos({ tramos = [], niveles = [], rutas = [] }) {
  const contenedor = useRef(null)
  const mapa = useRef(null)
  const capa = useRef(null)

  useEffect(() => {
    mapa.current = L.map(contenedor.current, { zoomControl: true, scrollWheelZoom: false, tap: true })
      .setView(CENTRO, 15)
    L.tileLayer(TILES, { attribution: ATRIBUCION, maxZoom: 19 }).addTo(mapa.current)
    capa.current = L.layerGroup().addTo(mapa.current)
    return () => { mapa.current.remove(); mapa.current = null }
  }, [])

  useEffect(() => {
    if (!mapa.current || !capa.current) return
    capa.current.clearLayers()
    const todos = []
    rutas.forEach((r) => {
      L.polyline(r.geometria, { color: '#0f3d3e', weight: 3, opacity: 0.55, dashArray: '6 8' })
        .bindTooltip(`Ruta alternativa: ${r.nombre}`).addTo(capa.current)
    })
    tramos.forEach((t) => {
      const n = niveles.find((x) => x.tramo_codigo === t.codigo)
      const color = n?.color ?? '#7a7a7a'
      const texto = n ? `${t.nombre}: ${n.etiqueta} (IPV ${n.ipv})` : t.nombre
      L.polyline(t.geometria, { color: '#fff', weight: 11, opacity: 0.95 }).addTo(capa.current)
      L.polyline(t.geometria, { color, weight: 7, opacity: 1, lineCap: 'round' })
        .bindTooltip(texto, { sticky: true }).addTo(capa.current)
      t.geometria.forEach((p) => todos.push(p))
    })
    if (todos.length) mapa.current.fitBounds(L.latLngBounds(todos), { padding: [24, 24], maxZoom: 16 })
  }, [tramos, niveles, rutas])

  return <div ref={contenedor} className="mapa" role="img" aria-label="Mapa de la Avenida Pradilla con el nivel de tráfico por tramo" />
}
