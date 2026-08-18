import { useEffect, useRef, useState } from 'react'
import { IconChevron } from './icons'

export function MultiSelect({
  label,
  options,
  selected,
  onChange,
}: {
  label: string
  options: string[]
  selected: string[]
  onChange: (next: string[]) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  function toggle(option: string) {
    if (selected.includes(option)) onChange(selected.filter((o) => o !== option))
    else onChange([...selected, option])
  }

  const summary =
    selected.length === options.length
      ? 'All'
      : selected.length === 0
        ? 'None'
        : selected.length <= 2
          ? selected.join(', ')
          : `${selected.length} selected`

  return (
    <div className="relative" ref={ref}>
      <label className="mb-1.5 block text-xs font-medium text-ink-muted">{label}</label>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between rounded-md border border-border bg-surface px-3 py-2 text-sm text-ink shadow-card"
      >
        <span className="truncate">{summary}</span>
        <IconChevron className={`h-4 w-4 shrink-0 text-ink-faint transition-transform ${open ? 'rotate-90' : ''}`} />
      </button>

      {open && (
        <div className="absolute z-10 mt-1 max-h-64 w-full overflow-auto rounded-md border border-border bg-surface py-1 shadow-card">
          <div className="flex gap-2 border-b border-border px-3 py-1.5">
            <button className="text-xs font-medium text-accent" onClick={() => onChange(options)}>
              Select all
            </button>
            <button className="text-xs font-medium text-ink-muted" onClick={() => onChange([])}>
              Clear
            </button>
          </div>
          {options.map((option) => (
            <label key={option} className="flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm text-ink hover:bg-canvas">
              <input type="checkbox" checked={selected.includes(option)} onChange={() => toggle(option)} className="accent-accent" />
              <span className="truncate">{option}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}
