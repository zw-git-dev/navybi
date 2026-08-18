import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Measure, Row, RowCount } from '../api/types'
import { Card, DataTable, ErrorNote, PageHeader, Spinner } from '../components/ui'

export function GovernancePage() {
  const cleansingLog = useQuery({ queryKey: ['gov-cleansing-log'], queryFn: () => api.get<Row[]>('/api/governance/cleansing-log') })
  const rowCounts = useQuery({ queryKey: ['gov-row-counts'], queryFn: () => api.get<RowCount[]>('/api/governance/row-counts') })
  const measures = useQuery({ queryKey: ['gov-measures'], queryFn: () => api.get<Measure[]>('/api/governance/measures') })

  if (cleansingLog.isLoading || rowCounts.isLoading || measures.isLoading) return <Spinner />
  if (cleansingLog.error || rowCounts.error || measures.error || !cleansingLog.data || !rowCounts.data || !measures.data) {
    return <ErrorNote message="Could not load the governance panel." />
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Data quality & governance" caption="Cleansing decisions, row-count reconciliation, and the measure glossary — made visible in-app rather than left as an external doc." />

      <section>
        <h2 className="mb-2 text-sm font-semibold text-ink">Cleansing log</h2>
        <p className="mb-3 text-xs text-ink-faint">Every automated cleansing decision applied to raw data before it entered the semantic layer, with row counts and reasons.</p>
        <Card className="p-3">
          <DataTable rows={cleansingLog.data} />
        </Card>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-ink">Row counts: raw vs. clean vs. semantic layer</h2>
        <Card className="p-3">
          <DataTable rows={rowCounts.data} />
        </Card>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-ink">Measure glossary</h2>
        <p className="mb-3 text-xs text-ink-faint">
          Plain-language definition of every measure, plus its DAX equivalent for Power BI — both defined together
          so they can't silently drift apart.
        </p>
        <div className="space-y-3">
          {measures.data.map((m) => (
            <details key={m.id} className="rounded-lg border border-border bg-surface p-4 shadow-card">
              <summary className="cursor-pointer text-sm font-medium text-ink">{m.label}</summary>
              <div className="mt-3 space-y-2 text-sm text-ink-muted">
                <p>{m.description}</p>
                <p className="text-xs">
                  View: <code className="rounded bg-canvas px-1.5 py-0.5">{m.table}</code>
                </p>
                <div>
                  <p className="mb-1 text-xs font-medium text-ink">DAX equivalent (for Power BI):</p>
                  <pre className="overflow-x-auto rounded-md bg-canvas p-3 text-xs text-ink">{m.dax || '-- not yet documented --'}</pre>
                </div>
                {m.power_query_notes && <p className="text-xs text-ink-faint">{m.power_query_notes}</p>}
              </div>
            </details>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-ink">What this prototype does and does not prove</h2>
        <Card className="space-y-3 p-5 text-sm text-ink-muted">
          <p>
            <span className="font-medium text-ink">Proven:</span> an end-to-end pipeline from messy synthetic data
            through logged cleansing to a governed semantic layer and dashboards/conversational answers that all
            trace to the same SQL and underlying rows.
          </p>
          <p>
            <span className="font-medium text-ink">Not proven:</span> real DoD data source connections, true
            natural-language understanding when falling back to the keyword matcher, DoD-grade identity (PKI/CAC),
            or an actual RMF assessment/Authority to Operate.
          </p>
        </Card>
      </section>
    </div>
  )
}
