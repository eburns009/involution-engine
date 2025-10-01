import { describe, it, expect, beforeEach, vi } from 'vitest'
import { loadSettings, saveSettings } from './settings'

describe('Settings persistence', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset localStorage mock
    const mockStorage = {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
    }
    Object.defineProperty(window, 'localStorage', {
      value: mockStorage,
      writable: true,
    })
  })

  it('loads defaults when no settings exist', () => {
    vi.mocked(localStorage.getItem).mockReturnValue(null)

    const settings = loadSettings()

    expect(settings.theme).toBe('light')
    expect(settings.houseSystem).toBe('whole-sign')
    expect(settings.columns).toEqual(['longitude', 'latitude', 'distance'])
  })

  it('persists and loads settings', () => {
    const mockSettings = {
      theme: 'astro' as const,
      houseSystem: 'equal' as const,
      columns: ['longitude'] as const,
      precision: { lon: 3, lat: 5, dist: 4 },
      units: { angle: 'dms' as const },
    }

    vi.mocked(localStorage.getItem).mockReturnValue(JSON.stringify(mockSettings))

    const loaded = loadSettings()
    expect(loaded.theme).toBe('astro')
    expect(loaded.houseSystem).toBe('equal')

    // Test saving
    saveSettings(loaded)
    expect(localStorage.setItem).toHaveBeenCalledWith(
      'involution.settings.v1',
      JSON.stringify(mockSettings)
    )
  })
})