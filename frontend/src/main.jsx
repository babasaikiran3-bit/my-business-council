import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AuthKitProvider } from '@workos-inc/authkit-react'
import './index.css'
import App from './App.jsx'
import { AuthConfigError } from './components/AuthGuard'

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
      <BrowserRouter>
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
          <App />
        </AuthKitProvider>
      </BrowserRouter>
    </StrictMode>,
  )
}
