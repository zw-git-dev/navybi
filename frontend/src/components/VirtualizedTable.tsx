import { useRef } from 'react'
import { useVirtualizer } from '@tanstack/react-virtual'

const ROW_HEIGHT = 36

// A windowed table for the two tables that can actually grow large
// (Drill-down's mission rows, and the audit log over time) -- only rows
// scrolled into view are ever in the DOM, so scroll performance doesn't
// degrade as row count grows. Built as a CSS grid (not a real <table>)
// specifically so the header and virtualized rows share one
// grid-template-columns definition and never drift out of alignment as
// rows scroll in and out, which is the usual snag with virtualizing an
// HTML table.
export function VirtualizedTable<T extends object>({ rows, height = 480 }: { rows: T[]; height?: number }) {
  const scrollRef = useRef<HTMLDivElement>(null)

  const virtualizer = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 12,
  })

  if (!rows.length) {
    return <p className="text-sm text-ink-faint">No rows.</p>
  }

  const columns = Object.keys(rows[0]) as (keyof T)[]
  const gridTemplateColumns = `repeat(${columns.length}, minmax(140px, 1fr))`

  return (
    <div className="rounded-md border border-border">
      <div className="overflow-x-auto">
        <div style={{ minWidth: columns.length * 140 }}>
          <div
            className="grid border-b border-border bg-canvas"
            style={{ gridTemplateColumns }}
          >
            {columns.map((col) => (
              <div
                key={String(col)}
                className="truncate px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-ink-faint"
              >
                {String(col)}
              </div>
            ))}
          </div>

          <div ref={scrollRef} className="overflow-y-auto" style={{ height }}>
            <div style={{ height: virtualizer.getTotalSize(), position: 'relative' }}>
              {virtualizer.getVirtualItems().map((virtualRow) => {
                const row = rows[virtualRow.index]
                return (
                  <div
                    key={virtualRow.key}
                    className={`grid text-sm ${virtualRow.index % 2 ? 'bg-canvas/40' : 'bg-white'} hover:bg-accent-soft/40`}
                    style={{
                      gridTemplateColumns,
                      position: 'absolute',
                      top: 0,
                      left: 0,
                      width: '100%',
                      height: virtualRow.size,
                      transform: `translateY(${virtualRow.start}px)`,
                    }}
                  >
                    {columns.map((col) => (
                      <div key={String(col)} className="truncate border-b border-border px-3 py-2 text-ink-muted">
                        {formatCell(row[col])}
                      </div>
                    ))}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function formatCell(value: unknown) {
  if (value === null || value === undefined) return <span className="text-ink-faint">—</span>
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return String(value)
}
