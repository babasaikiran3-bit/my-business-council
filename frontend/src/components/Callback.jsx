import { useEffect } from 'react'
import { useAuth } from '@workos-inc/authkit-react'
import { useNavigate } from 'react-router-dom'

/**
 * Callback component that handles the OAuth redirect from WorkOS.
 * The AuthKitProvider handles the actual callback processing automatically.
 * This component just waits for auth to complete and redirects.
 */
export function Callback() {
  const { isLoading, user } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!isLoading) {
      // Redirect to home regardless - AuthGuard will handle unauthenticated state
      navigate('/', { replace: true })
    }
  }, [isLoading, navigate])

  // Show loading state while AuthKitProvider processes the callback
  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
        <p className="text-muted-foreground">Signing in...</p>
      </div>
    </div>
  )
}

