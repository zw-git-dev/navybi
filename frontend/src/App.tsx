import { lazy, Suspense } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { ProtectedRoute } from './ProtectedRoute'
import { AppShell } from './components/AppShell'
import { LoginPage } from './pages/Login'
import { Spinner } from './components/ui'

// Lazy-loaded per route so the initial bundle (login + app shell) doesn't
// pay for Recharts and react-leaflet/Leaflet upfront -- those only load
// once a user actually navigates to a page that uses them.
const OverviewPage = lazy(() => import('./pages/Overview').then((m) => ({ default: m.OverviewPage })))
const TrendsPage = lazy(() => import('./pages/Trends').then((m) => ({ default: m.TrendsPage })))
const MapPage = lazy(() => import('./pages/MapPage').then((m) => ({ default: m.MapPage })))
const AskPage = lazy(() => import('./pages/Ask').then((m) => ({ default: m.AskPage })))
const DrilldownPage = lazy(() => import('./pages/Drilldown').then((m) => ({ default: m.DrilldownPage })))
const GovernancePage = lazy(() => import('./pages/Governance').then((m) => ({ default: m.GovernancePage })))
const AuditLogPage = lazy(() => import('./pages/AuditLog').then((m) => ({ default: m.AuditLogPage })))

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
})

function RouteFallback() {
  return (
    <div className="flex justify-center">
      <Spinner />
    </div>
  )
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <AppShell />
                  </ProtectedRoute>
                }
              >
                <Route index element={<OverviewPage />} />
                <Route path="trends" element={<TrendsPage />} />
                <Route path="map" element={<MapPage />} />
                <Route path="ask" element={<AskPage />} />
                <Route path="drilldown" element={<DrilldownPage />} />
                <Route
                  path="governance"
                  element={
                    <ProtectedRoute requireAdmin>
                      <GovernancePage />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="audit-log"
                  element={
                    <ProtectedRoute requireAdmin>
                      <AuditLogPage />
                    </ProtectedRoute>
                  }
                />
              </Route>
            </Routes>
          </Suspense>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
