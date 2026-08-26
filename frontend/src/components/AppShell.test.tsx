import { describe, expect, it } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { AppShell } from './AppShell'
import { ADMIN, ANALYST, mockApi, renderWithProviders } from '../test/utils'

const SHARED_NAV = ['Overview', 'Trends', 'Map', 'Ask a question', 'Drill-down']
const ADMIN_NAV = ['Data quality & governance', 'Audit log']

describe('AppShell navigation', () => {
  it('shows the admin-only sections to an admin', async () => {
    mockApi({ '/api/auth/me': ADMIN })
    renderWithProviders(<AppShell />)

    await waitFor(() => expect(screen.getByText('Demo Administrator')).toBeInTheDocument())
    for (const label of [...SHARED_NAV, ...ADMIN_NAV]) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
  })

  it('hides the admin-only sections from an analyst', async () => {
    // This is the client-side half of the role gating. It's a UI courtesy,
    // not the enforcement -- the API independently returns 403 (covered in
    // tests/test_api.py). Both halves are tested because relying on either
    // one alone is how role gating quietly breaks.
    mockApi({ '/api/auth/me': ANALYST })
    renderWithProviders(<AppShell />)

    await waitFor(() => expect(screen.getByText('Demo Analyst')).toBeInTheDocument())
    for (const label of SHARED_NAV) {
      expect(screen.getByText(label)).toBeInTheDocument()
    }
    for (const label of ADMIN_NAV) {
      expect(screen.queryByText(label)).not.toBeInTheDocument()
    }
  })

  it('identifies the signed-in user and their role', async () => {
    mockApi({ '/api/auth/me': ANALYST })
    renderWithProviders(<AppShell />)

    await waitFor(() => expect(screen.getByText('Demo Analyst')).toBeInTheDocument())
    expect(screen.getByText('analyst')).toBeInTheDocument()
  })

  it('offers a way to sign out', async () => {
    mockApi({ '/api/auth/me': ADMIN })
    renderWithProviders(<AppShell />)

    await waitFor(() => expect(screen.getByTitle('Sign out')).toBeInTheDocument())
  })
})
