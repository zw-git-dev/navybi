// Backend month columns arrive as full ISO timestamps (e.g.
// "2026-03-01T00:00:00") since they're just DATE/TIMESTAMP columns from
// DuckDB serialized as-is -- format them as "Mar 2026" for axis labels
// without touching the underlying data.
export function formatMonthTick(value: string) {
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  return d.toLocaleDateString(undefined, { month: 'short', year: 'numeric' })
}
