import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Row } from '../../api/types'
import { colorForCategory } from '../../lib/palette'
import { tooltipStyle, axisTick, gridStroke } from './chartTheme'

export function CategoryBarChart({
  data,
  xKey,
  yKey,
  colorKey,
  height = 260,
}: {
  data: Row[]
  xKey: string
  yKey: string
  colorKey?: string
  height?: number
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
        <XAxis
          dataKey={xKey}
          tick={axisTick}
          angle={-30}
          textAnchor="end"
          height={64}
          interval={0}
        />
        <YAxis tick={axisTick} />
        <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(42,92,219,0.06)' }} />
        <Bar dataKey={yKey} radius={[3, 3, 0, 0]} maxBarSize={40}>
          {data.map((row, i) => (
            <Cell key={i} fill={colorKey ? colorForCategory(String(row[colorKey])) : 'var(--color-accent)'} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
