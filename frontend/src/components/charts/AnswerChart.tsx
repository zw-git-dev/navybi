import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from 'recharts'
import type { ChartSpec, Row } from '../../api/types'
import { pivotForMultiLine } from '../../lib/pivot'
import { colorForCategory } from '../../lib/palette'
import { formatMonthTick } from '../../lib/format'
import { axisTick, gridStroke, tooltipStyle } from './chartTheme'

function isMonthColumn(key: string) {
  return key.toLowerCase().includes('month')
}

export function AnswerChart({ chart, df }: { chart: ChartSpec; df: Row[] }) {
  if (chart.kind === 'bar') {
    return (
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={df} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
          <XAxis dataKey={chart.x} tick={axisTick} angle={-25} textAnchor="end" height={70} interval={0} />
          <YAxis tick={axisTick} />
          <Tooltip contentStyle={tooltipStyle} cursor={{ fill: 'rgba(42,92,219,0.06)' }} />
          <Bar dataKey={chart.y} fill="var(--color-accent)" radius={[3, 3, 0, 0]} maxBarSize={48} />
        </BarChart>
      </ResponsiveContainer>
    )
  }

  if (chart.color) {
    const { data, seriesNames } = pivotForMultiLine(df, chart.x, chart.color, chart.y)
    return (
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
          <XAxis dataKey={chart.x} tick={axisTick} tickFormatter={isMonthColumn(chart.x) ? formatMonthTick : undefined} />
          <YAxis tick={axisTick} />
          <Tooltip contentStyle={tooltipStyle} labelFormatter={isMonthColumn(chart.x) ? (label) => formatMonthTick(String(label)) : undefined} />
          <Legend wrapperStyle={{ fontSize: 11, color: '#5b6270' }} />
          {seriesNames.map((name) => (
            <Line key={name} type="monotone" dataKey={name} stroke={colorForCategory(name)} strokeWidth={2} dot={{ r: 2.5 }} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={df} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} vertical={false} />
        <XAxis dataKey={chart.x} tick={axisTick} tickFormatter={isMonthColumn(chart.x) ? formatMonthTick : undefined} />
        <YAxis tick={axisTick} />
        <Tooltip contentStyle={tooltipStyle} labelFormatter={isMonthColumn(chart.x) ? (label) => formatMonthTick(String(label)) : undefined} />
        <Line type="monotone" dataKey={chart.y} stroke="var(--color-accent)" strokeWidth={2} dot={{ r: 2.5 }} />
      </LineChart>
    </ResponsiveContainer>
  )
}
