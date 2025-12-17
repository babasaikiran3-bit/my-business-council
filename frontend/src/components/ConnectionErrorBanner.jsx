import { WifiOff, RefreshCw, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useConnectionError } from '@/contexts/ConnectionErrorContext'
import { cn } from '@/lib/utils'

/**
 * ConnectionErrorBanner - Displays a prominent banner when backend is unavailable.
 *
 * Features:
 * - Fixed position at top of viewport (z-50)
 * - Destructive color scheme for visibility
 * - WiFi-off icon for clear visual indication
 * - Retry button to attempt reconnection
 * - Dismiss button to hide the banner
 * - Loading state during retry attempts
 *
 * Accessibility:
 * - role="alert" for screen readers
 * - aria-live="assertive" for immediate announcement
 */
export function ConnectionErrorBanner() {
  const { connectionError, isRetrying, retryConnection, clearConnectionError } = useConnectionError()

  if (!connectionError) {
    return null
  }

  return (
    <div
      className={cn(
        'fixed top-0 left-0 right-0 z-50',
        'bg-destructive text-destructive-foreground',
        'px-4 py-3 shadow-lg'
      )}
      role="alert"
      aria-live="assertive"
    >
      <div className="container mx-auto flex items-center justify-between gap-4">
        {/* Icon and Message */}
        <div className="flex items-center gap-3">
          <WifiOff className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
          <span className="text-sm font-medium">
            {connectionError.message}
          </span>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={retryConnection}
            disabled={isRetrying}
            className="gap-1.5"
          >
            <RefreshCw
              className={cn('h-4 w-4', isRetrying && 'animate-spin')}
              aria-hidden="true"
            />
            {isRetrying ? 'Retrying...' : 'Retry'}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            onClick={clearConnectionError}
            className="h-8 w-8 text-destructive-foreground hover:bg-destructive/80"
            aria-label="Dismiss error"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  )
}

export default ConnectionErrorBanner

