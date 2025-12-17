import { useEffect, useRef } from 'react'
import { useConnectionError } from '@/contexts/ConnectionErrorContext'
import { api } from '@/api'

/**
 * ApiConnectionHandler - Bridges the API client to the ConnectionError React context.
 *
 * This component serves two purposes:
 * 1. Sets up a callback so the API client can report connection errors to React
 * 2. Performs an initial health check on mount to detect if the backend is down
 *
 * React StrictMode Handling:
 * - Uses a ref to track if health check has run
 * - Resets the ref in cleanup so remounts work correctly
 * - Runs health check synchronously (no setTimeout delays)
 *
 * This component must be placed inside ConnectionErrorProvider and renders its children.
 */
export function ApiConnectionHandler({ children }) {
  const { reportConnectionError } = useConnectionError()
  const healthCheckDone = useRef(false)

  useEffect(() => {
    // Set the callback so API client can report errors to React context
    api.setConnectionErrorCallback(reportConnectionError)

    // Perform initial health check (only once, handles StrictMode double-mount)
    if (!healthCheckDone.current) {
      healthCheckDone.current = true
      api.checkHealth()
    }

    // Cleanup: remove callback and reset health check flag
    return () => {
      api.setConnectionErrorCallback(null)
      healthCheckDone.current = false
    }
  }, [reportConnectionError])

  return children
}

export default ApiConnectionHandler

