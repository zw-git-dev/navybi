import type { ReactNode } from 'react'

export function PageHeader({ title, caption }: { title: string; caption?: ReactNode }) {
  return (
    <div className="mb-6">
      <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
      {caption && <p className="mt-1 max-w-3xl text-sm text-ink-muted">{caption}</p>}
    </div>
  )
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-border bg-surface shadow-card ${className}`}>{children}</div>
  )
}

export function ChartCard({
  title,
  caption,
  children,
  footer,
}: {
  title: string
  caption?: string
  children: ReactNode
  footer?: ReactNode
}) {
  return (
    <Card className="flex flex-col p-5">
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {caption && <p className="mt-0.5 text-xs text-ink-faint">{caption}</p>}
      </div>
      <div className="min-h-0 flex-1">{children}</div>
      {footer && <div className="mt-3 border-t border-border pt-2 text-xs text-ink-faint">{footer}</div>}
    </Card>
  )
}

export function KpiCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card className="p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-faint">{label}</div>
      <div className="mt-2 text-[26px] font-semibold tabular-nums leading-none text-ink">{value}</div>
      {sub && <div className="mt-1.5 text-xs text-ink-muted">{sub}</div>}
    </Card>
  )
}

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-ink-muted">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-accent" />
      {label}
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-bad/30 bg-bad-soft px-4 py-3 text-sm text-bad">{message}</div>
  )
}

export function Badge({ tone = 'neutral', children }: { tone?: 'neutral' | 'accent' | 'good' | 'warn' | 'bad'; children: ReactNode }) {
  const tones: Record<string, string> = {
    neutral: 'bg-canvas text-ink-muted border-border',
    accent: 'bg-accent-soft text-accent border-accent/20',
    good: 'bg-good-soft text-good border-good/20',
    warn: 'bg-warn-soft text-warn border-warn/20',
    bad: 'bg-bad-soft text-bad border-bad/20',
  }
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  )
}

export function DataTable<T extends object>({ rows, maxHeight = '420px' }: { rows: T[]; maxHeight?: string }) {
  if (!rows.length) {
    return <p className="text-sm text-ink-faint">No rows.</p>
  }
  const columns = Object.keys(rows[0]) as (keyof T)[]
  return (
    <div className="overflow-auto rounded-md border border-border" style={{ maxHeight }}>
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 bg-canvas">
          <tr>
            {columns.map((col) => (
              <th key={String(col)} className="whitespace-nowrap border-b border-border px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-ink-faint">
                {String(col)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="odd:bg-white even:bg-canvas/40 hover:bg-accent-soft/40">
              {columns.map((col) => (
                <td key={String(col)} className="whitespace-nowrap border-b border-border px-3 py-2 text-ink-muted">
                  {formatCell(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function formatCell(value: unknown) {
  if (value === null || value === undefined) return <span className="text-ink-faint">—</span>
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return String(value)
}

export function downloadCsv<T extends object>(filename: string, rows: T[]) {
  if (!rows.length) return
  const columns = Object.keys(rows[0]) as (keyof T)[]
  const escape = (v: unknown) => {
    const s = v === null || v === undefined ? '' : String(v)
    return s.includes(',') || s.includes('"') || s.includes('\n') ? `"${s.replace(/"/g, '""')}"` : s
  }
  const lines = [columns.join(','), ...rows.map((r) => columns.map((c) => escape(r[c])).join(','))]
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function Button({
  children,
  onClick,
  variant = 'primary',
  type = 'button',
  className = '',
  disabled,
}: {
  children: ReactNode
  onClick?: () => void
  variant?: 'primary' | 'secondary'
  type?: 'button' | 'submit'
  className?: string
  disabled?: boolean
}) {
  const base = 'inline-flex items-center justify-center gap-1.5 rounded-md px-3.5 py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed'
  const variants: Record<string, string> = {
    primary: 'bg-accent text-white hover:bg-accent-hover',
    secondary: 'border border-border bg-surface text-ink hover:bg-canvas',
  }
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`${base} ${variants[variant]} ${className}`}>
      {children}
    </button>
  )
}
