import { useEffect, useRef } from 'react'
import { api } from '../api'
import { useConnectionError } from '@/contexts/ConnectionErrorContext'

/**
 * ApiConnectionHandler - Bridges the API client to the ConnectionError React context.
 *
 * This component serves two purposes:
 * 1. Connects the API client's error reporting to the React context system
 * 2. Performs an initial health check to detect backend unavailability on app load
 *
 * Placement in component tree:
 * - Must be inside ConnectionErrorProvider (to access context)
 * - Must be inside AuthKitProvider (for auth context)
 * - Should wrap the main app content
 *
 * React StrictMode Handling:
 * In development, React StrictMode double-invokes effects to detect issues.
 * This component handles it by:
 * - Using a ref (healthCheckDone) to track if health check has run
 * - Resetting the ref in cleanup so remounts work correctly
 * - Running health check synchronously in the effect (no setTimeout delays)
 *   to ensure it runs before cleanup cancels it
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Child components to render
 */
export function ApiConnectionHandler({ children }) {
  const { reportConnectionError } = useConnectionError()
  const healthCheckDone = useRef(false)

  // Combined effect: set up callback AND run health check
  // These are combined because the health check needs the callback to be set first
  useEffect(() => {
    // Connect the API client to report connection errors via the context
    api.setConnectionErrorCallback(reportConnectionError)

    // Run health check immediately (only once per mount cycle)
    // Using a ref that resets on cleanup handles React StrictMode double-mounting
    if (!healthCheckDone.current) {
      healthCheckDone.current = true
      api.checkHealth()
    }

    // Cleanup on unmount
    return () => {
      api.setConnectionErrorCallback(null)
      // Reset ref so health check runs again if component remounts
      healthCheckDone.current = false
    }
  }, [reportConnectionError])

  return children
}

export default ApiConnectionHandler

