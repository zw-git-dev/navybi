import { describe, expect, it } from 'vitest'
import { formatMonthTick } from './format'

describe('formatMonthTick', () => {
  it('turns a DuckDB timestamp into a short month label', () => {
    // The raw value is what the API actually sends -- a full ISO timestamp,
    // since these are DATE/TIMESTAMP columns serialized as-is.
    expect(formatMonthTick('2026-03-01T00:00:00')).toMatch(/Mar/)
    expect(formatMonthTick('2026-03-01T00:00:00')).toMatch(/2026/)
  })

  it('passes through a value it cannot parse instead of rendering "Invalid Date"', () => {
    // Axis labels are cosmetic; a surprising value should degrade to showing
    // the raw string rather than putting "Invalid Date" on a chart.
    expect(formatMonthTick('not a date')).toBe('not a date')
  })

  it('leaves an already-short label alone when unparseable', () => {
    expect(formatMonthTick('Q1')).toBe('Q1')
  })
})
