// Muted, enterprise-BI categorical palette -- one accent-family blue plus a
// handful of desaturated complements, deliberately not a rainbow.
export const CATEGORY_COLORS = [
  '#2A5CDB',
  '#3FA796',
  '#E2A72E',
  '#C2588B',
  '#6A5ACD',
  '#4C9A4C',
  '#B24E3A',
  '#5B7A94',
]

const cache = new Map<string, string>()

export function colorForCategory(category: string) {
  if (cache.has(category)) return cache.get(category) as string
  const color = CATEGORY_COLORS[cache.size % CATEGORY_COLORS.length]
  cache.set(category, color)
  return color
}
