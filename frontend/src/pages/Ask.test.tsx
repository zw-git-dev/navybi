import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AskPage } from './Ask'
import { ADMIN, mockApi, renderWithProviders } from '../test/utils'

const META = { sample_questions: ['What is the mission completion rate by unit?'], llm_configured: true, llm_model: 'test/model' }

const ANSWER_WITH_CAVEAT = {
  understood: true,
  question: 'readiness trend by month',
  sql: 'SELECT * FROM v_avg_readiness_by_unit',
  df: [{ unit_name: 'Alpha', avg_readiness_pct: 79 }],
  chart: { kind: 'bar', x: 'unit_name', y: 'avg_readiness_pct', color: null },
  measure_label: 'Average equipment readiness by unit',
  measure_description: 'Average readiness_pct across all equipment types for a unit.',
  matched_entity: null,
  source_table: 'v_avg_readiness_by_unit',
  caveats: ['this measure has no time dimension, so the "by month" part of your question was not answered'],
  window_note: null,
  interpreted_by: 'llm',
}

const NOT_UNDERSTOOD = {
  understood: false,
  question: 'what is the weather',
  sql: null,
  df: [],
  chart: null,
  measure_label: null,
  measure_description: null,
  matched_entity: null,
  caveats: [],
  interpreted_by: null,
}

describe('AskPage', () => {
  it('surfaces a caveat prominently alongside the answer', async () => {
    // The central safety behavior of this app: when only part of a question
    // can be answered, the unanswered part must be stated loudly rather than
    // dropped, because a rendered chart gives the reader no reason to doubt
    // it. See QUESTION_TEST_LOG.md.
    mockApi({ '/api/auth/me': ADMIN, '/api/ask/meta': META, '/api/ask': ANSWER_WITH_CAVEAT })
    renderWithProviders(<AskPage />)

    await waitFor(() => expect(screen.getByPlaceholderText(/mission completion rate/i)).toBeInTheDocument())
    await userEvent.type(screen.getByPlaceholderText(/mission completion rate/i), 'readiness trend by month')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    await waitFor(() => expect(screen.getByText(/Partial answer/)).toBeInTheDocument())
    expect(screen.getByText(/no time dimension/)).toBeInTheDocument()
  })

  it('shows the SQL and measure definition so an answer can be verified', async () => {
    mockApi({ '/api/auth/me': ADMIN, '/api/ask/meta': META, '/api/ask': ANSWER_WITH_CAVEAT })
    renderWithProviders(<AskPage />)

    await waitFor(() => expect(screen.getByPlaceholderText(/mission completion rate/i)).toBeInTheDocument())
    await userEvent.type(screen.getByPlaceholderText(/mission completion rate/i), 'readiness')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    await waitFor(() => expect(screen.getByText(/SELECT \* FROM v_avg_readiness_by_unit/)).toBeInTheDocument())
    expect(screen.getByText(/Average readiness_pct across all equipment types/)).toBeInTheDocument()
  })

  it('names which interpreter produced the answer', async () => {
    mockApi({ '/api/auth/me': ADMIN, '/api/ask/meta': META, '/api/ask': ANSWER_WITH_CAVEAT })
    renderWithProviders(<AskPage />)

    await waitFor(() => expect(screen.getByPlaceholderText(/mission completion rate/i)).toBeInTheDocument())
    await userEvent.type(screen.getByPlaceholderText(/mission completion rate/i), 'readiness')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    // Matched exactly rather than by /LLM/, since the page's own caption also
    // mentions the LLM -- the assertion needs to be about the interpreter
    // badge on the answer, not any mention of the word.
    await waitFor(() => expect(screen.getByText('🤖 LLM')).toBeInTheDocument())
  })

  it('says it did not understand rather than showing an empty chart', async () => {
    mockApi({ '/api/auth/me': ADMIN, '/api/ask/meta': META, '/api/ask': NOT_UNDERSTOOD })
    renderWithProviders(<AskPage />)

    await waitFor(() => expect(screen.getByPlaceholderText(/mission completion rate/i)).toBeInTheDocument())
    await userEvent.type(screen.getByPlaceholderText(/mission completion rate/i), 'what is the weather')
    await userEvent.click(screen.getByRole('button', { name: 'Ask' }))

    await waitFor(() => expect(screen.getByText(/Neither interpreter recognized/)).toBeInTheDocument())
  })

  it('will not submit an empty question', async () => {
    mockApi({ '/api/auth/me': ADMIN, '/api/ask/meta': META })
    renderWithProviders(<AskPage />)

    await waitFor(() => expect(screen.getByRole('button', { name: 'Ask' })).toBeInTheDocument())
    expect(screen.getByRole('button', { name: 'Ask' })).toBeDisabled()
  })
})
