import { describe, it, expect } from 'vitest'

// Helper functions for house calculations
function normalize360(angle: number): number {
  return ((angle % 360) + 360) % 360
}

function wholeSignCusps(siderealAsc: number): number[] {
  const house1 = Math.floor(siderealAsc / 30) * 30
  return Array.from({ length: 12 }, (_, i) => normalize360(house1 + i * 30))
}

function equalCusps(siderealAsc: number): number[] {
  return Array.from({ length: 12 }, (_, i) => normalize360(siderealAsc + i * 30))
}

describe('Houses invariants', () => {
  it('Equal-House cusps are 12 steps of 30° from ASC', () => {
    const asc = 123.456
    const eq = equalCusps(asc)

    for (let i = 1; i < 12; i++) {
      const d = (eq[i] - eq[i-1] + 360) % 360
      expect(Math.abs(d - 30)).toBeLessThan(1e-9)
    }
  })

  it('Whole-Sign cusp 1 is floor(ASC/30)*30', () => {
    const asc = 299.9
    const ws = wholeSignCusps(asc)
    expect(ws[0]).toBe(270)  // floor(299.9/30)*30 = floor(9.99)*30 = 9*30 = 270
  })

  it('Whole-Sign cusps are aligned to sign boundaries', () => {
    const asc = 156.7  // middle of Leo (150-180)
    const ws = wholeSignCusps(asc)
    expect(ws[0]).toBe(150)  // Leo starts at 150°
    expect(ws[1]).toBe(180)  // Virgo starts at 180°
    expect(ws[11]).toBe(120) // Cancer starts at 120°
  })

  it('All house systems produce 12 cusps', () => {
    const asc = 45.5
    const ws = wholeSignCusps(asc)
    const eq = equalCusps(asc)

    expect(ws).toHaveLength(12)
    expect(eq).toHaveLength(12)
  })

  it('normalize360 handles edge cases correctly', () => {
    expect(normalize360(0)).toBe(0)
    expect(normalize360(360)).toBe(0)
    expect(normalize360(361)).toBe(1)
    expect(normalize360(-1)).toBe(359)
    expect(normalize360(-361)).toBe(359)
  })
})