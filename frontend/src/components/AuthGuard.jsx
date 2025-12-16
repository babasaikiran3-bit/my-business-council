import { useAuth } from '@workos-inc/authkit-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from './ui/card'
import { Button } from './ui/button'
import { AlertTriangle } from 'lucide-react'

/**
 * Error component shown when authentication is not configured.
 * This is a secure failure state - no access is granted.
 */
export function AuthConfigError() {
  return (
    <div className="flex h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-md mx-4">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center">
            <AlertTriangle className="h-6 w-6 text-destructive" />
          </div>
          <CardTitle className="text-2xl">Configuration Error</CardTitle>
          <CardDescription>
            Authentication not configured. Please contact your administrator.
          </CardDescription>
        </CardHeader>
        <CardContent className="text-center">
          <p className="text-xs text-muted-foreground">
            The application cannot start because required authentication credentials are missing.
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

/**
 * AuthGuard component that protects routes requiring authentication.
 * Shows a sign-in screen if the user is not authenticated.
 * Always requires authentication - no bypass logic.
 */
export function AuthGuard({ children }) {
  const { isLoading, user, signIn } = useAuth()

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    )
  }

  if (!user) {
    // Show sign-in screen with shadcn/ui components
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Card className="w-full max-w-md mx-4">
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">Eternal Copilot</CardTitle>
            <CardDescription>
              Sign in with your Eternal account to continue
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4">
            <Button
              onClick={() => signIn()}
              size="lg"
              className="w-full"
            >
              Sign In with Microsoft
            </Button>
            <p className="text-xs text-muted-foreground text-center">
              Only @eternal.ag email addresses are allowed
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return children
}

/**
 * Hook to get the current authenticated user's information.
 * Returns user details extracted from the WorkOS user object.
 */
export function useCurrentUser() {
  const { user } = useAuth()

  // Extract metadata from WorkOS user object
  const metadata = user?.publicMetadata || {}

  return {
    id: user?.id,
    email: user?.email,
    name: user?.firstName && user?.lastName
      ? `${user.firstName} ${user.lastName}`
      : user?.email,
    imageUrl: user?.profilePictureUrl,
    role: metadata.role || 'user',
    userType: metadata.user_type || 'employee',
    organizationId: metadata.organization_id,
    authMethod: user?.ssoProfile?.connectionType || 'password',
  }
}

