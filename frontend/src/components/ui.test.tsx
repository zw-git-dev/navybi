import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DataTable, downloadCsv } from './ui'

describe('DataTable', () => {
  it('renders a column header per key and a row per record', () => {
    render(<DataTable rows={[{ unit: 'Alpha', rate: 64.1 }, { unit: 'Bravo', rate: 60 }]} />)
    expect(screen.getByText('unit')).toBeInTheDocument()
    expect(screen.getByText('Alpha')).toBeInTheDocument()
    expect(screen.getByText('60')).toBeInTheDocument()
  })

  it('shows a dash for a missing value rather than blank or "null"', () => {
    // The dataset intentionally contains missing values (undated missions,
    // absent durations). Rendering a literal "null" or an empty cell would
    // read as a rendering bug; an em-dash reads as "not recorded".
    render(<DataTable rows={[{ unit: 'Alpha', duration: null }]} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('renders booleans as Yes/No instead of true/false', () => {
    render(<DataTable rows={[{ resolved: true, understood: false }]} />)
    expect(screen.getByText('Yes')).toBeInTheDocument()
    expect(screen.getByText('No')).toBeInTheDocument()
  })

  it('says so plainly when there are no rows', () => {
    render(<DataTable rows={[]} />)
    expect(screen.getByText('No rows.')).toBeInTheDocument()
  })
})

describe('downloadCsv', () => {
  function captureCsv(rows: Record<string, unknown>[]) {
    let captured = ''
    vi.stubGlobal('URL', {
      createObjectURL: (blob: Blob) => {
        // Blob.text() is async; read the buffer the constructor was given by
        // stubbing Blob itself instead, so the assertion stays synchronous.
        void blob
        return 'blob:stub'
      },
      revokeObjectURL: () => {},
    })
    const OriginalBlob = globalThis.Blob
    vi.stubGlobal(
      'Blob',
      class extends OriginalBlob {
        constructor(parts: BlobPart[], opts?: BlobPropertyBag) {
          super(parts, opts)
          captured = String(parts[0])
        }
      },
    )
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    downloadCsv('test.csv', rows)
    return captured
  }

  it('writes a header row followed by the data rows', () => {
    const csv = captureCsv([{ unit: 'Alpha', rate: 64.1 }])
    expect(csv.split('\n')[0]).toBe('unit,rate')
    expect(csv.split('\n')[1]).toBe('Alpha,64.1')
  })

  it('quotes a value containing a comma so columns do not shift', () => {
    // Unit names and cleansing reasons contain commas; unquoted, they'd split
    // into extra columns and silently corrupt the export.
    const csv = captureCsv([{ note: 'Alpha, Bravo' }])
    expect(csv.split('\n')[1]).toBe('"Alpha, Bravo"')
  })

  it('escapes embedded double quotes by doubling them', () => {
    const csv = captureCsv([{ note: 'said "hello"' }])
    expect(csv.split('\n')[1]).toBe('"said ""hello"""')
  })

  it('quotes a value containing a newline', () => {
    const csv = captureCsv([{ note: 'line one\nline two' }])
    expect(csv).toContain('"line one\nline two"')
  })

  it('writes an empty cell for null rather than the text "null"', () => {
    const csv = captureCsv([{ unit: 'Alpha', duration: null }])
    expect(csv.split('\n')[1]).toBe('Alpha,')
  })

  it('does nothing when there is nothing to export', () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    downloadCsv('empty.csv', [])
    expect(clickSpy).not.toHaveBeenCalled()
  })
})
