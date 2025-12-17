import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { AuthKitProvider } from '@workos-inc/authkit-react'
import { Toaster } from 'sonner'
import { onCLS, onFCP, onLCP, onTTFB } from 'web-vitals'
import './index.css'
import App from './App.jsx'
import { AuthConfigError } from './components/AuthGuard'
import { ConnectionErrorProvider } from './contexts/ConnectionErrorContext'
import { ConnectionErrorBanner } from './components/ConnectionErrorBanner'
import { ApiConnectionHandler } from './components/ApiConnectionHandler'

// Create a data router to support useBlocker hook for navigation blocking
// This is required for React Router v6.4+ features like useBlocker
const router = createBrowserRouter([
  {
    path: '*',
    element: <App />,
  },
])

// Report Core Web Vitals in production for performance monitoring
// These metrics help track:
// - CLS (Cumulative Layout Shift): Visual stability
// - FCP (First Contentful Paint): Initial render speed
// - LCP (Largest Contentful Paint): Main content load time
// - TTFB (Time to First Byte): Server response time
if (import.meta.env.PROD) {
  const reportWebVitals = (metric) => {
    console.log('[Web Vitals]', metric.name, metric.value)
    // TODO: Send to analytics service
    // Example: analytics.track('web-vital', metric)
  }
  onCLS(reportWebVitals)
  onFCP(reportWebVitals)
  onLCP(reportWebVitals)
  onTTFB(reportWebVitals)
}

const WORKOS_CLIENT_ID = import.meta.env.VITE_WORKOS_CLIENT_ID
const WORKOS_REDIRECT_URI = import.meta.env.VITE_WORKOS_REDIRECT_URI

// If WorkOS client ID is missing, render error screen
if (!WORKOS_CLIENT_ID) {
  console.error('CRITICAL: VITE_WORKOS_CLIENT_ID not set. Authentication cannot proceed.')
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <AuthConfigError />
    </StrictMode>,
  )
} else {
  // Normal app with authentication
  // Session duration is configured in the WorkOS Dashboard (Authentication section):
  // - Maximum session length: 7 days (168 hours)
  // - Inactivity timeout: 7 days
  // - Access token duration: 5-15 minutes (short for security, auto-refreshed)
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <ConnectionErrorProvider>
        <AuthKitProvider
          clientId={WORKOS_CLIENT_ID}
          redirectUri={WORKOS_REDIRECT_URI}
          // Refresh tokens 60 seconds before they expire to ensure seamless session continuity
          // This prevents any gap where the user might be logged out momentarily
          refreshBufferInterval={60}
          // Optional: Handle refresh failures (e.g., session expired server-side)
          onRefreshFailure={(error) => {
            console.error('Session refresh failed:', error.message)
            // Session has expired or been revoked - user will need to sign in again
            // The SDK will automatically show the sign-in screen via AuthGuard
          }}
        >
          <ApiConnectionHandler>
            {/* Connection error banner - displays at top when backend is unavailable */}
            <ConnectionErrorBanner />
            {/* Use RouterProvider instead of BrowserRouter to support useBlocker hook */}
            <RouterProvider router={router} />
            {/* Toast notification container - positioned top-right with rich color styling */}
            <Toaster position="top-right" richColors closeButton />
          </ApiConnectionHandler>
        </AuthKitProvider>
      </ConnectionErrorProvider>
    </StrictMode>,
  )
}
