export interface User {
  username: string
  role: 'admin' | 'analyst'
  display_name: string
}

export interface OverviewData {
  kpis: {
    total_missions: number
    overall_completion_pct: number
    overall_readiness_pct: number
    overall_training_currency_pct: number
  }
  completion_by_unit: Row[]
  readiness_by_unit: Row[]
  training_by_unit: Row[]
  downtime_by_equipment: Row[]
  resolution_by_unit: Row[]
  completion_measure_description: string
}

export interface TrendsData {
  units: string[]
  mission_count_by_month: Row[]
  avg_duration_by_type: Row[]
}

export interface MapData {
  statuses: string[]
  missions: Row[]
}

export interface DrilldownData {
  units: string[]
  missions: Row[]
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Row = Record<string, any>

export interface ChartSpec {
  kind: 'bar' | 'line'
  x: string
  y: string
  color: string | null
}

export interface AskResult {
  understood: boolean
  question: string
  sql: string | null
  df: Row[]
  chart: ChartSpec | null
  measure_label: string | null
  measure_description: string | null
  matched_entity: string | null
  source_table?: string
  caveats: string[]
  window_note?: string | null
  interpreted_by: string | null
}

export interface AskMeta {
  sample_questions: string[]
  llm_configured: boolean
  llm_model: string
}

export interface Measure {
  id: string
  label: string
  description: string
  table: string
  dax: string
  power_query_notes: string
}

export interface RowCount {
  table: string
  source_format: string
  raw_row_count: number
  clean_row_count: number
  rows_removed_or_flagged: number
}

export interface AuditLogEntry {
  timestamp_utc: string
  username: string
  role: string
  question: string
  understood: boolean
  interpreted_by: string
  caveat_count: number
}
