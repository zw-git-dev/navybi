import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { TrendsData } from '../api/types'
import { CategoryBarChart } from '../components/charts/CategoryBarChart'
import { MultiLineChart } from '../components/charts/MultiLineChart'
import { pivotForMultiLine } from '../lib/pivot'
import { ChartCard, ErrorNote, PageHeader, Spinner } from '../components/ui'
import { MultiSelect } from '../components/MultiSelect'

export function TrendsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['trends'],
    queryFn: () => api.get<TrendsData>('/api/dashboard/trends'),
  })
  const [selectedUnits, setSelectedUnits] = useState<string[] | null>(null)

  const units = data?.units ?? []
  const activeUnits = selectedUnits ?? units

  const filteredByMonth = useMemo(
    () => (data ? data.mission_count_by_month.filter((r) => activeUnits.includes(r.unit_name)) : []),
    [data, activeUnits],
  )
  const { data: lineData, seriesNames } = useMemo(
    () => pivotForMultiLine(filteredByMonth, 'mission_month', 'unit_name', 'mission_count'),
    [filteredByMonth],
  )

  if (isLoading) return <Spinner />
  if (error || !data) return <ErrorNote message="Could not load trends." />

  return (
    <div>
      <PageHeader title="Trends" caption="Mission volume over time and average duration by mission type." />

      <div className="mb-4 max-w-sm">
        <MultiSelect label="Units" options={units} selected={activeUnits} onChange={setSelectedUnits} />
      </div>

      <div className="mb-4">
        <ChartCard title="Mission count by month">
          <MultiLineChart data={lineData} xKey="mission_month" seriesNames={seriesNames} />
        </ChartCard>
      </div>

      <ChartCard title="Average mission duration by type" caption="Hours; missions with missing/invalid duration are excluded from the average">
        <CategoryBarChart data={data.avg_duration_by_type} xKey="mission_type" yKey="avg_duration_hours" />
      </ChartCard>
    </div>
  )
}
