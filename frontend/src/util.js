export const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
export const DIAS_CORTO = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

// Día (0 = lunes) y hora actuales en Colombia, sin depender de la zona horaria del dispositivo
export function ahoraBogota(fecha = new Date()) {
  const partes = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/Bogota', weekday: 'short', hour: 'numeric', hourCycle: 'h23',
  }).formatToParts(fecha)
  const wd = partes.find((p) => p.type === 'weekday').value
  const hora = parseInt(partes.find((p) => p.type === 'hour').value, 10)
  const mapa = { Mon: 0, Tue: 1, Wed: 2, Thu: 3, Fri: 4, Sat: 5, Sun: 6 }
  return { dia: mapa[wd], hora }
}

export const fmtHora = (h) => `${String(h).padStart(2, '0')}:00`

// Mismos umbrales que el backend (KAN-44): fluido 0-33, moderado 34-66, congestionado 67-100
export function clasificar(ipv) {
  if (ipv <= 33) return { nivel: 'fluido', etiqueta: 'Fluido', color: '#2e8540' }
  if (ipv <= 66) return { nivel: 'moderado', etiqueta: 'Moderado', color: '#c98f00' }
  return { nivel: 'congestionado', etiqueta: 'Congestionado', color: '#c0392b' }
}

export const ICONO_NIVEL = { fluido: '●', moderado: '▲', congestionado: '■' }
