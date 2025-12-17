import { createContext, useContext, useState, useCallback, useRef } from 'react'

/**
 * ConnectionErrorContext - Global state management for backend connectivity errors.
 *
 * This context enables the app to display a prominent banner when the backend
 * becomes unavailable, providing users with clear feedback and retry options.
 *
 * Architecture:
 * - ConnectionErrorProvider: Wraps app at root level (in main.jsx)
 * - useConnectionError: Hook for components to access error state and actions
 * - ConnectionErrorBanner: Consumes context to display/hide the UI banner
 * - ApiConnectionHandler: Reports errors from the API client to this context
 *
 * Error Flow:
 * 1. API client detects network failure (in api.js)
 * 2. API client calls the callback set by ApiConnectionHandler
 * 3. Callback invokes reportConnectionError() in this context
 * 4. Context state updates, causing ConnectionErrorBanner to render
 * 5. User can retry or dismiss the error
 */
const ConnectionErrorContext = createContext(null)

/**
 * Connection error types for categorizing different failure modes.
 */
export const CONNECTION_ERROR_TYPES = {
  NETWORK_ERROR: 'NETWORK_ERROR',  // Server unreachable, no internet
  TIMEOUT: 'TIMEOUT',               // Request exceeded time limit
  SERVER_ERROR: 'SERVER_ERROR',     // 5xx HTTP status codes
}

/**
 * Check if an error indicates a connection/network problem.
 * Used by components to distinguish connection errors from other types.
 *
 * @param {Error} error - The error to check
 * @returns {boolean} True if this is a connection error
 */
export function isConnectionError(error) {
  if (!error) return false
  if (error instanceof TypeError && error.message.includes('fetch')) return true
  if (error.message?.toLowerCase().includes('network')) return true
  if (error.message?.toLowerCase().includes('failed to fetch')) return true
  if (error.message?.toLowerCase().includes('connection refused')) return true
  if (error.message?.toLowerCase().includes('cors')) return true
  if (error.message?.toLowerCase().includes('err_connection')) return true
  return false
}

/**
 * Check if an HTTP status code indicates a server-side error.
 * @param {number} status - HTTP status code
 * @returns {boolean} True if status is 5xx
 */
export function isServerError(status) {
  return status >= 500 && status < 600
}

/**
 * Provider component that manages connection error state.
 * Should wrap the entire app to make error state globally accessible.
 */
export function ConnectionErrorProvider({ children }) {
  const [connectionError, setConnectionError] = useState(null)
  const [isRetrying, setIsRetrying] = useState(false)
  const retryCallbackRef = useRef(null)

  /**
   * Report a connection error to display the banner.
   * @param {Object} params - Error parameters
   * @param {string} params.type - Error type from CONNECTION_ERROR_TYPES
   * @param {string} params.message - User-friendly error message
   * @param {Function} [params.retryFn] - Optional function to retry the failed operation
   */
  const reportConnectionError = useCallback(({ type, message, retryFn }) => {
    setConnectionError({ type, message, timestamp: Date.now() })
    retryCallbackRef.current = retryFn || null
  }, [])

  /**
   * Clear the connection error and reset retry state.
   */
  const clearConnectionError = useCallback(() => {
    setConnectionError(null)
    retryCallbackRef.current = null
    setIsRetrying(false)
  }, [])

  /**
   * Attempt to retry the failed operation.
   */
  const retryConnection = useCallback(async () => {
    if (!retryCallbackRef.current) {
      clearConnectionError()
      return
    }

    setIsRetrying(true)
    try {
      await retryCallbackRef.current()
      clearConnectionError()
    } catch {
      // Retry failed, keep error displayed
      setIsRetrying(false)
    }
  }, [clearConnectionError])

  const value = {
    connectionError,
    isRetrying,
    reportConnectionError,
    clearConnectionError,
    retryConnection,
  }

  return (
    <ConnectionErrorContext.Provider value={value}>
      {children}
    </ConnectionErrorContext.Provider>
  )
}

/**
 * Hook to access connection error state and actions.
 * Must be used within a ConnectionErrorProvider.
 */
export function useConnectionError() {
  const context = useContext(ConnectionErrorContext)
  if (!context) {
    throw new Error('useConnectionError must be used within a ConnectionErrorProvider')
  }
  return context
}

export default ConnectionErrorContext

