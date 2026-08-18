import type { Row } from '../api/types'

// Recharts wants one row per x-value with one column per series, but the
// API returns long-format rows (x, series, value) -- e.g. one row per
// (month, unit) pair. This reshapes that into the wide format Recharts
// needs and returns the distinct series names in first-seen order (for
// stable line ordering/coloring).
export function pivotForMultiLine(rows: Row[], xKey: string, seriesKey: string, valueKey: string) {
  const byX = new Map<string, Row>()
  const seriesNames: string[] = []
  const seenSeries = new Set<string>()

  for (const row of rows) {
    const x = row[xKey]
    const series = String(row[seriesKey])
    if (!seenSeries.has(series)) {
      seenSeries.add(series)
      seriesNames.push(series)
    }
    if (!byX.has(x)) byX.set(x, { [xKey]: x })
    byX.get(x)![series] = row[valueKey]
  }

  const data = Array.from(byX.values()).sort((a, b) => (a[xKey] > b[xKey] ? 1 : -1))
  return { data, seriesNames }
}
