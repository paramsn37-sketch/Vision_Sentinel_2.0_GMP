import { QueryClientProvider } from '@tanstack/react-query'
import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Navigate, RouterProvider, useLocation } from 'react-router'
import { Toaster } from 'sonner'
import { AppShell } from '@/components/shell/AppShell'
import { Skeleton, TooltipProvider } from '@/components/ui'
import { setUnauthorizedHandler } from '@/lib/api/client'
import { queryClient } from '@/lib/queryClient'
import { useMe } from '@/lib/api/hooks'
import { LoginPage } from '@/features/auth/LoginPage'
import { useUI } from '@/stores/ui'

const LivePage = lazy(() => import('@/features/live/LivePage'))
const IncidentsPage = lazy(() => import('@/features/incidents/IncidentsPage'))
const ZonesPage = lazy(() => import('@/features/zones/ZonesPage'))
const AnalyticsPage = lazy(() => import('@/features/analytics/AnalyticsPage'))
const UploadsPage = lazy(() => import('@/features/uploads/UploadsPage'))
const ModelPage = lazy(() => import('@/features/model/ModelPage'))
const SettingsPage = lazy(() => import('@/features/settings/SettingsPage'))
const DesignPage = lazy(() => import('@/features/design/DesignPage'))


function RequireAuth({ children }: { children: ReactNode }) {
  const me = useMe()
  const loc = useLocation()
  if (me.isPending) return <PageSkeleton />
  if (me.isError) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />
  return children
}

function PageSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-6" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-7 w-48" />
      <Skeleton className="h-64 w-full" />
    </div>
  )
}

const page = (el: ReactNode) => <Suspense fallback={<PageSkeleton />}>{el}</Suspense>

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  ...(import.meta.env.DEV ? [{ path: '/_design', element: page(<DesignPage />) }] : []),
  {
    path: '/',
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <Navigate to="/live" replace /> },
      { path: 'live', element: page(<LivePage />) },
      { path: 'incidents', element: page(<IncidentsPage />) },
      { path: 'zones', element: page(<ZonesPage />) },
      { path: 'analytics', element: page(<AnalyticsPage />) },
      { path: 'uploads', element: page(<UploadsPage />) },
      { path: 'model', element: page(<ModelPage />) },
      { path: 'settings', element: page(<SettingsPage />) },
      { path: '*', element: <Navigate to="/live" replace /> },
    ],
  },
])

setUnauthorizedHandler(() => {
  queryClient.removeQueries({ queryKey: ['me'] })
  if (location.pathname !== '/login') router.navigate(`/login?next=${encodeURIComponent(location.pathname)}`)
})

export function App() {
  const theme = useUI((s) => s.theme)
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <RouterProvider router={router} />
        <Toaster
          theme={theme}
          position="bottom-right"
          visibleToasts={4}
          closeButton
          toastOptions={{
            classNames: {
              toast: '!bg-raised !border-line !text-fg !rounded-md !shadow-float !font-sans',
              description: '!text-muted',
              actionButton: '!bg-accent !text-on-accent !rounded-sm',
            },
          }}
        />
      </TooltipProvider>
    </QueryClientProvider>
  )
}
