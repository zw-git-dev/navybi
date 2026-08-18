import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { DrilldownData } from '../api/types'
import { Button, Card, downloadCsv, ErrorNote, PageHeader, Spinner } from '../components/ui'
import { MultiSelect } from '../components/MultiSelect'
import { VirtualizedTable } from '../components/VirtualizedTable'

export function DrilldownPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['drilldown'],
    queryFn: () => api.get<DrilldownData>('/api/dashboard/drilldown'),
  })
  const [selectedUnits, setSelectedUnits] = useState<string[] | null>(null)

  const units = data?.units ?? []
  const activeUnits = selectedUnits ?? units
  const rows = useMemo(
    () => (data ? data.missions.filter((m) => activeUnits.includes(m.unit_name)) : []),
    [data, activeUnits],
  )

  if (isLoading) return <Spinner />
  if (error || !data) return <ErrorNote message="Could not load drill-down data." />

  return (
    <div>
      <PageHeader
        title="Drill-down / manual verification"
        caption="This is the raw semantic-layer table backing the dashboards — use it to spot-check any number by hand."
      />

      <div className="mb-4 flex items-end justify-between gap-4">
        <div className="max-w-sm flex-1">
          <MultiSelect label="Filter by unit" options={units} selected={activeUnits} onChange={setSelectedUnits} />
        </div>
        <Button variant="secondary" onClick={() => downloadCsv('missions_filtered.csv', rows)}>
          Download CSV
        </Button>
      </div>

      <Card className="p-3">
        <VirtualizedTable rows={rows} height={640} />
      </Card>
    </div>
  )
}
