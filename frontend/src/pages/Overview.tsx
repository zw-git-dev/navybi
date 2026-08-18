import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { OverviewData } from '../api/types'
import { CategoryBarChart } from '../components/charts/CategoryBarChart'
import { ChartCard, ErrorNote, KpiCard, PageHeader, Spinner } from '../components/ui'

export function OverviewPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['overview'],
    queryFn: () => api.get<OverviewData>('/api/dashboard/overview'),
  })

  if (isLoading) return <Spinner />
  if (error || !data) return <ErrorNote message="Could not load the overview dashboard." />

  return (
    <div>
      <PageHeader
        title="Overview"
        caption="Fleet-wide KPIs across missions, readiness, training currency, and maintenance — all computed from the governed semantic layer."
      />

      <div className="mb-6 grid grid-cols-4 gap-4">
        <KpiCard label="Total missions" value={data.kpis.total_missions.toLocaleString()} sub="Valid, dated records" />
        <KpiCard label="Objective completion" value={`${data.kpis.overall_completion_pct}%`} />
        <KpiCard label="Avg. equipment readiness" value={`${data.kpis.overall_readiness_pct}%`} />
        <KpiCard label="Training / cert currency" value={`${data.kpis.overall_training_currency_pct}%`} />
      </div>

      <div className="mb-4 grid grid-cols-3 gap-4">
        <ChartCard title="Mission completion rate by unit" caption="% of missions with a known, met objective">
          <CategoryBarChart data={data.completion_by_unit} xKey="unit_name" yKey="completion_rate_pct" colorKey="community" />
        </ChartCard>
        <ChartCard title="Average equipment readiness by unit">
          <CategoryBarChart data={data.readiness_by_unit} xKey="unit_name" yKey="avg_readiness_pct" colorKey="community" />
        </ChartCard>
        <ChartCard title="Training / cert currency rate by unit">
          <CategoryBarChart data={data.training_by_unit} xKey="unit_name" yKey="currency_rate_pct" colorKey="community" />
        </ChartCard>
      </div>

      <h2 className="mb-3 mt-8 text-sm font-semibold uppercase tracking-wide text-ink-faint">Maintenance</h2>
      <div className="grid grid-cols-2 gap-4">
        <ChartCard title="Average maintenance downtime by equipment type" caption="Hours per discrepancy event">
          <CategoryBarChart data={data.downtime_by_equipment} xKey="equipment_type" yKey="avg_downtime_hours" />
        </ChartCard>
        <ChartCard title="Discrepancy resolution rate by unit">
          <CategoryBarChart data={data.resolution_by_unit} xKey="unit_name" yKey="resolution_rate_pct" colorKey="community" />
        </ChartCard>
      </div>
      <p className="mt-3 text-xs text-ink-faint">
        Maintenance events are sourced from an actual SQL database (SQLite), not a flat file.
      </p>
    </div>
  )
}
