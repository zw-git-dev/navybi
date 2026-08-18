import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { AuditLogEntry } from '../api/types'
import { Button, Card, downloadCsv, ErrorNote, PageHeader, Spinner } from '../components/ui'
import { VirtualizedTable } from '../components/VirtualizedTable'

export function AuditLogPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['audit-log'],
    queryFn: () => api.get<AuditLogEntry[]>('/api/audit-log'),
  })

  if (isLoading) return <Spinner />
  if (error || !data) return <ErrorNote message="Could not load the audit log." />

  return (
    <div>
      <div className="mb-4 flex items-start justify-between gap-4">
        <PageHeader
          title="Audit log"
          caption="Every conversational query answered by this app — who asked it, when, and which interpreter answered it."
        />
        {data.length > 0 && (
          <Button variant="secondary" onClick={() => downloadCsv('audit_log.csv', data)}>
            Download CSV
          </Button>
        )}
      </div>

      {data.length === 0 ? (
        <Card className="p-6 text-sm text-ink-muted">No queries logged yet. Ask a question on the "Ask a question" page to populate this log.</Card>
      ) : (
        <Card className="p-3">
          <VirtualizedTable rows={data} height={640} />
        </Card>
      )}
    </div>
  )
}
