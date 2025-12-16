import { useAuth } from '@workos-inc/authkit-react'
import { useCurrentUser } from './AuthGuard'
import { Button } from './ui/button'
import { LogOut } from 'lucide-react'

/**
 * UserMenu component that displays the current user's information
 * and provides a sign-out button.
 */
export default function UserMenu() {
  const { signOut } = useAuth()
  const user = useCurrentUser()

  return (
    <div className="flex items-center gap-3 p-3 border-t border-border">
      {user.imageUrl ? (
        <img
          src={user.imageUrl}
          alt={user.name}
          className="w-8 h-8 rounded-full flex-shrink-0"
        />
      ) : (
        <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-sm font-medium flex-shrink-0">
          {user.name?.charAt(0) || user.email?.charAt(0) || '?'}
        </div>
      )}
      <div className="flex flex-col min-w-0 flex-1">
        <span className="text-sm font-medium truncate">{user.name}</span>
        <span className="text-xs text-muted-foreground truncate">{user.email}</span>
      </div>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => signOut({ returnTo: window.location.origin })}
        title="Sign Out"
        className="flex-shrink-0"
      >
        <LogOut className="h-4 w-4" />
      </Button>
    </div>
  )
}

