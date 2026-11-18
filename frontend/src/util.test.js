import { describe, expect, it } from 'vitest'
import { ahoraBogota, clasificar, fmtHora } from './util.js'

describe('clasificar', () => {
  it('respeta los umbrales del IPV', () => {
    expect(clasificar(0).nivel).toBe('fluido')
    expect(clasificar(33).nivel).toBe('fluido')
    expect(clasificar(34).nivel).toBe('moderado')
    expect(clasificar(66).nivel).toBe('moderado')
    expect(clasificar(67).nivel).toBe('congestionado')
  })
})

describe('ahoraBogota', () => {
  it('usa la hora de Colombia (UTC-5)', () => {
    // Martes 17 nov 2026, 22:30 UTC = 17:30 en Bogotá
    expect(ahoraBogota(new Date('2026-11-17T22:30:00Z'))).toEqual({ dia: 1, hora: 17 })
    // Cambio de día: lunes 02:00 UTC = domingo 21:00 en Bogotá
    expect(ahoraBogota(new Date('2026-11-16T02:00:00Z'))).toEqual({ dia: 6, hora: 21 })
  })
})

describe('fmtHora', () => {
  it('rellena con ceros', () => expect(fmtHora(7)).toBe('07:00'))
})
