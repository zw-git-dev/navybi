import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { AskMeta, AskResult } from '../api/types'
import { Badge, Button, Card, DataTable, ErrorNote, PageHeader } from '../components/ui'
import { AnswerChart } from '../components/charts/AnswerChart'

const INTERPRETER_LABELS: Record<string, { text: string; tone: 'accent' | 'neutral' | 'warn' }> = {
  llm: { text: '🤖 LLM', tone: 'accent' },
  keyword: { text: '🔤 Keyword/entity matcher (fallback)', tone: 'neutral' },
  keyword_after_llm_no_match: { text: '🔤 Keyword matcher (LLM found no match, this is a partial answer)', tone: 'warn' },
  llm_corrected_by_keyword_domain_check: { text: '🤖 LLM — corrected by a keyword-based sanity check', tone: 'warn' },
}

export function AskPage() {
  const [question, setQuestion] = useState('')
  const { data: meta } = useQuery({ queryKey: ['ask-meta'], queryFn: () => api.get<AskMeta>('/api/ask/meta') })

  const mutation = useMutation({
    mutationFn: (q: string) => api.post<AskResult>('/api/ask', { question: q }),
  })

  function submit(q: string) {
    setQuestion(q)
    mutation.mutate(q)
  }

  const result = mutation.data
  const interpreterInfo = result?.interpreted_by ? INTERPRETER_LABELS[result.interpreted_by] : null

  return (
    <div>
      <PageHeader
        title="Ask a question"
        caption={
          meta?.llm_configured
            ? `Type a plain-language question about missions, readiness, training, or maintenance. Interpreted by a real LLM (${meta.llm_model} via OpenRouter), with a keyword/entity matcher as a fallback if the LLM call fails or is rate-limited.`
            : 'Type a plain-language question about missions or readiness. No LLM is configured — questions are interpreted with a keyword/entity matcher.'
        }
      />

      {meta && meta.sample_questions.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-2">
          {meta.sample_questions.map((sample) => (
            <button
              key={sample}
              onClick={() => submit(sample)}
              className="rounded-full border border-border bg-surface px-3 py-1.5 text-xs text-ink-muted hover:border-accent hover:text-accent"
            >
              {sample}
            </button>
          ))}
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (question.trim()) submit(question)
        }}
        className="mb-6 flex gap-2"
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. What is the mission completion rate by unit?"
          className="flex-1 rounded-md border border-border bg-surface px-3.5 py-2.5 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
        />
        <Button type="submit" disabled={mutation.isPending || !question.trim()}>
          {mutation.isPending ? 'Interpreting…' : 'Ask'}
        </Button>
      </form>

      {mutation.isError && <ErrorNote message="Something went wrong answering that question." />}

      {result && !result.understood && (
        <Card className="p-5">
          <p className="text-sm text-ink-muted">
            Neither interpreter recognized that question as matching a supported measure (mission completion,
            readiness, mission duration, mission-count trends, training currency, or maintenance), optionally
            filtered by a unit, mission type, equipment type, or certification name.
          </p>
        </Card>
      )}

      {result && result.understood && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {interpreterInfo && <Badge tone={interpreterInfo.tone}>{interpreterInfo.text}</Badge>}
          </div>

          {result.caveats.length > 0 && (
            <div className="space-y-2">
              {result.caveats.map((c, i) => (
                <div key={i} className="rounded-md border border-warn/30 bg-warn-soft px-4 py-3 text-sm text-warn">
                  ⚠️ Partial answer — {c}
                </div>
              ))}
            </div>
          )}

          <Card className="p-5">
            <h3 className="mb-3 text-sm font-semibold text-ink">{result.measure_label}</h3>
            {result.chart && <AnswerChart chart={result.chart} df={result.df} />}
          </Card>

          <details className="rounded-lg border border-border bg-surface p-5 shadow-card" open>
            <summary className="cursor-pointer text-sm font-semibold text-ink">Explain this answer</summary>
            <div className="mt-3 space-y-2 text-sm text-ink-muted">
              <p>
                <span className="font-medium text-ink">What this measures:</span> {result.measure_description}
              </p>
              <div>
                <span className="font-medium text-ink">Query executed against the semantic layer:</span>
                <pre className="mt-1 overflow-x-auto rounded-md bg-canvas p-3 text-xs text-ink">{result.sql}</pre>
              </div>
              {result.matched_entity && (
                <p>
                  <span className="font-medium text-ink">Filter applied:</span> {result.matched_entity}
                </p>
              )}
              {result.window_note && (
                <p>
                  <span className="font-medium text-ink">Time window applied:</span> {result.window_note}
                </p>
              )}
              <p>
                <span className="font-medium text-ink">Source view (for manual verification):</span>{' '}
                <code className="rounded bg-canvas px-1.5 py-0.5 text-xs">{result.source_table}</code> — see the
                Drill-down page.
              </p>
            </div>
          </details>

          <Card className="p-3">
            <DataTable rows={result.df} />
          </Card>
        </div>
      )}
    </div>
  )
}
