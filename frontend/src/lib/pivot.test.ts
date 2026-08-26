import { describe, expect, it } from 'vitest'
import { pivotForMultiLine } from './pivot'

// The API returns long-format rows (one per month/unit pair) but Recharts
// needs wide format (one row per month, one column per unit). Getting this
// reshape subtly wrong produces a chart that renders without error but plots
// the wrong thing -- the exact class of failure this project treats as worse
// than a crash -- so it's worth pinning down precisely.
describe('pivotForMultiLine', () => {
  const rows = [
    { mission_month: '2026-02-01', unit_name: 'Alpha', mission_count: 3 },
    { mission_month: '2026-02-01', unit_name: 'Bravo', mission_count: 9 },
    { mission_month: '2026-03-01', unit_name: 'Alpha', mission_count: 30 },
    { mission_month: '2026-03-01', unit_name: 'Bravo', mission_count: 11 },
  ]

  it('collapses long rows into one row per x-value', () => {
    const { data } = pivotForMultiLine(rows, 'mission_month', 'unit_name', 'mission_count')
    expect(data).toEqual([
      { mission_month: '2026-02-01', Alpha: 3, Bravo: 9 },
      { mission_month: '2026-03-01', Alpha: 30, Bravo: 11 },
    ])
  })

  it('returns series names in first-seen order so colors stay stable', () => {
    const { seriesNames } = pivotForMultiLine(rows, 'mission_month', 'unit_name', 'mission_count')
    expect(seriesNames).toEqual(['Alpha', 'Bravo'])
  })

  it('deduplicates series names rather than repeating them per row', () => {
    const { seriesNames } = pivotForMultiLine(rows, 'mission_month', 'unit_name', 'mission_count')
    expect(seriesNames).toHaveLength(2)
  })

  it('sorts by x-value even when the input is unordered', () => {
    const shuffled = [rows[2], rows[0], rows[3], rows[1]]
    const { data } = pivotForMultiLine(shuffled, 'mission_month', 'unit_name', 'mission_count')
    expect(data.map((r) => r.mission_month)).toEqual(['2026-02-01', '2026-03-01'])
  })

  it('leaves a series absent for an x-value it has no row for', () => {
    // A unit that flew no missions in a month simply has no row. It must come
    // through as undefined (a gap the line connects across), never as 0 --
    // "no data recorded" and "zero missions" are different claims, and this
    // codebase is deliberate about not conflating them.
    const sparse = [
      { mission_month: '2026-02-01', unit_name: 'Alpha', mission_count: 3 },
      { mission_month: '2026-03-01', unit_name: 'Alpha', mission_count: 30 },
      { mission_month: '2026-03-01', unit_name: 'Bravo', mission_count: 11 },
    ]
    const { data } = pivotForMultiLine(sparse, 'mission_month', 'unit_name', 'mission_count')
    expect(data[0].Bravo).toBeUndefined()
    expect(data[0].Bravo).not.toBe(0)
  })

  it('handles an empty input without throwing', () => {
    const { data, seriesNames } = pivotForMultiLine([], 'mission_month', 'unit_name', 'mission_count')
    expect(data).toEqual([])
    expect(seriesNames).toEqual([])
  })
})
