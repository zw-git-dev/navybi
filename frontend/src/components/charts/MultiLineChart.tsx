import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Row } from '../../api/types'
import { colorForCategory } from '../../lib/palette'
import { formatMonthTick } from '../../lib/format'
import { axisTick, gridStroke, tooltipStyle } from './chartTheme'

export function MultiLineChart({
  data,
  xKey,
  seriesNames,
  height = 280,
}: {
  data: Row[]
  xKey: string
  seriesNames: string[]
  height?: number
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
        <XAxis dataKey={xKey} tick={axisTick} tickFormatter={formatMonthTick} />
        <YAxis tick={axisTick} />
        <Tooltip contentStyle={tooltipStyle} labelFormatter={(label) => formatMonthTick(String(label))} />
        <Legend wrapperStyle={{ fontSize: 11, color: '#5b6270' }} />
        {seriesNames.map((name) => (
          <Line
            key={name}
            type="monotone"
            dataKey={name}
            stroke={colorForCategory(name)}
            strokeWidth={2}
            dot={{ r: 2.5 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  )
}
