import { WifiOff, RefreshCw, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useConnectionError, CONNECTION_ERROR_TYPES } from '@/contexts/ConnectionErrorContext'
import { cn } from '@/lib/utils'

/**
 * ConnectionErrorBanner - Prominent UI banner for backend connectivity errors.
 *
 * Displays when:
 * - Initial health check fails (backend not running)
 * - Any API call fails due to network issues
 * - Server returns 5xx errors
 *
 * Features:
 * - Fixed position at top of viewport (z-50)
 * - Destructive color scheme (red) for high visibility
 * - Animated entrance (slide-in-from-top)
 * - Retry button with loading spinner
 * - Dismiss button to hide banner
 * - Accessible with role="alert" and aria-live
 *
 * The banner automatically renders when connectionError state is set
 * in ConnectionErrorContext, and hides when state is cleared.
 */
export function ConnectionErrorBanner() {
  const { connectionError, isRetrying, retryConnection, clearConnectionError } = useConnectionError()

  // Don't render if no error
  if (!connectionError) {
    return null
  }

  // Get appropriate message based on error type, with fallbacks
  const getMessage = () => {
    switch (connectionError.type) {
      case CONNECTION_ERROR_TYPES.NETWORK_ERROR:
        return connectionError.message || 'Dashboard has lost connection to the server. Please check your network connection.'
      case CONNECTION_ERROR_TYPES.TIMEOUT:
        return connectionError.message || 'Request timed out. The server may be overloaded or unreachable.'
      case CONNECTION_ERROR_TYPES.SERVER_ERROR:
        return connectionError.message || 'Server error occurred. Please try again later.'
      default:
        return connectionError.message || 'Connection error occurred.'
    }
  }

  return (
    <div
      className={cn(
        'fixed top-0 left-0 right-0 z-50',
        'bg-destructive text-destructive-foreground',
        'px-4 py-3',
        'flex items-center justify-between gap-4',
        'shadow-lg',
        'animate-in slide-in-from-top duration-300'
      )}
      role="alert"
      aria-live="assertive"
    >
      <div className="flex items-center gap-3">
        <WifiOff className="h-5 w-5 shrink-0" />
        <div className="flex flex-col gap-0.5">
          <span className="font-medium">Connection Lost</span>
          <span className="text-sm opacity-90">{getMessage()}</span>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={retryConnection}
          disabled={isRetrying}
          className="bg-destructive-foreground/10 hover:bg-destructive-foreground/20 text-destructive-foreground border-0"
        >
          <RefreshCw className={cn('h-4 w-4 mr-1.5', isRetrying && 'animate-spin')} />
          {isRetrying ? 'Retrying...' : 'Retry'}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={clearConnectionError}
          className="h-8 w-8 hover:bg-destructive-foreground/10 text-destructive-foreground"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

export default ConnectionErrorBanner

