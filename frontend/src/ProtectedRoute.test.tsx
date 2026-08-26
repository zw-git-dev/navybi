import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { ProtectedRoute } from './ProtectedRoute'
import { ADMIN, ANALYST, mockApi, renderWithProviders } from './test/utils'

function Harness() {
  return (
    <Routes>
      <Route path="/login" element={<div>login page</div>} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <div>overview page</div>
          </ProtectedRoute>
        }
      />
      <Route
        path="/governance"
        element={
          <ProtectedRoute requireAdmin>
            <div>governance page</div>
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}

describe('ProtectedRoute', () => {
  it('sends an unauthenticated visitor to the login page', async () => {
    mockApi({}, { unauthenticated: true })
    renderWithProviders(<Harness />, { route: '/' })

    await waitFor(() => expect(screen.getByText('login page')).toBeInTheDocument())
  })

  it('lets an authenticated user through', async () => {
    mockApi({ '/api/auth/me': ANALYST })
    renderWithProviders(<Harness />, { route: '/' })

    await waitFor(() => expect(screen.getByText('overview page')).toBeInTheDocument())
  })

  it('redirects an analyst away from an admin-only route', async () => {
    // Deep-linking or typing the URL directly must not get an analyst onto an
    // admin page just because the nav link was hidden.
    mockApi({ '/api/auth/me': ANALYST })
    renderWithProviders(<Harness />, { route: '/governance' })

    await waitFor(() => expect(screen.getByText('overview page')).toBeInTheDocument())
    expect(screen.queryByText('governance page')).not.toBeInTheDocument()
  })

  it('allows an admin onto an admin-only route', async () => {
    mockApi({ '/api/auth/me': ADMIN })
    renderWithProviders(<Harness />, { route: '/governance' })

    await waitFor(() => expect(screen.getByText('governance page')).toBeInTheDocument())
  })

  it('does not flash the login page while the session is still loading', async () => {
    // Redirecting before /api/auth/me resolves would bounce an
    // already-signed-in user to the login screen on every refresh.
    mockApi({ '/api/auth/me': ADMIN })
    renderWithProviders(<Harness />, { route: '/' })

    expect(screen.queryByText('login page')).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('overview page')).toBeInTheDocument())
  })
})
