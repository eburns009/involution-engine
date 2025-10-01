import { test, expect } from '@playwright/test'

test('ephemeris end-to-end calculation', async ({ page }) => {
  await page.goto('/ephemeris?birth_time=2024-06-21T18:00:00Z&lat=37.7749&lon=-122.4194&elev=50&ayanamsa=lahiri')

  // Wait for the form to be loaded
  await expect(page.getByText('Ephemeris Calculator')).toBeVisible()

  // Submit calculation
  await page.getByRole('button', { name: /calculate/i }).click()

  // Wait for results
  await expect(page.getByText('Planetary Positions')).toBeVisible({ timeout: 30000 })

  // Verify SPICE metadata is displayed
  await expect(page.locator('text=ECLIPDATE')).toBeVisible()

  // Verify Sun position is displayed
  await expect(page.getByText('Sun')).toBeVisible()

  // Verify plugin panels are loaded
  await expect(page.getByText('Major Aspects')).toBeVisible()
  await expect(page.getByText('Houses & Angles')).toBeVisible()
})

test('settings persistence and house system switching', async ({ page }) => {
  await page.goto('/ephemeris')

  // Open settings
  await page.getByText('⚙️ Settings').click()
  await expect(page.getByText('Display Settings')).toBeVisible()

  // Change house system
  await page.getByRole('button', { name: 'equal' }).click()

  // Close settings
  await page.getByText('✕').click()

  // Perform calculation
  await page.getByRole('button', { name: /calculate/i }).click()
  await expect(page.getByText('Planetary Positions')).toBeVisible({ timeout: 30000 })

  // Verify Equal Houses is shown
  await expect(page.getByText('Equal Cusps')).toBeVisible()

  // Reload page and check persistence
  await page.reload()
  await page.getByRole('button', { name: /calculate/i }).click()
  await expect(page.getByText('Equal Cusps')).toBeVisible({ timeout: 30000 })
})

test('share link functionality', async ({ page }) => {
  await page.goto('/ephemeris')

  // Fill form with specific values
  await page.fill('input[type="datetime-local"]', '2024-12-25T12:00')
  await page.fill('input[placeholder*="Latitude"], input[type="number"]:nth-of-type(1)', '40.7128')
  await page.fill('input[placeholder*="Longitude"], input[type="number"]:nth-of-type(2)', '-74.0060')

  // Calculate
  await page.getByRole('button', { name: /calculate/i }).click()
  await expect(page.getByText('Planetary Positions')).toBeVisible({ timeout: 30000 })

  // Check that URL contains parameters
  expect(page.url()).toContain('birth_time=')
  expect(page.url()).toContain('lat=40.7128')
  expect(page.url()).toContain('lon=-74.0060')
})