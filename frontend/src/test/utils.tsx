import type { ReactNode } from 'react'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { AuthProvider } from '../auth/AuthContext'
import type { User } from '../api/types'

export const ADMIN: User = { username: 'admin', role: 'admin', display_name: 'Demo Administrator' }
export const ANALYST: User = { username: 'analyst', role: 'analyst', display_name: 'Demo Analyst' }

/**
 * Stubs window.fetch from a URL-substring -> response-body map, so a test can
 * describe just the endpoints it cares about. Anything unmapped fails loudly
 * rather than silently returning undefined -- a test that accidentally hits an
 * unstubbed endpoint should tell you, not quietly pass on empty data.
 */
export function mockApi(routes: Record<string, unknown>, options: { unauthenticated?: boolean } = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString()

    if (options.unauthenticated && url.includes('/api/auth/me')) {
      return new Response(JSON.stringify({ detail: 'Not authenticated' }), { status: 401 })
    }

    const match = Object.keys(routes).find((key) => url.includes(key))
    if (match === undefined) {
      throw new Error(`Unstubbed request in test: ${url}`)
    }
    return new Response(JSON.stringify(routes[match]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function renderWithProviders(ui: ReactNode, { route = '/' }: { route?: string } = {}) {
  // retry:false keeps a deliberately-failing request from stalling the test
  // for the length of react-query's backoff schedule.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <AuthProvider>{ui}</AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
