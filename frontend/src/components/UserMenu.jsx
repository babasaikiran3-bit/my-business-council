import { useAuth } from '@workos-inc/authkit-react'
import { useCurrentUser } from './AuthGuard'
import { Avatar, AvatarFallback, AvatarImage } from './ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from './ui/dropdown-menu'
import {
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  useSidebar,
} from './ui/sidebar'
import { LogOut, ChevronsUpDown } from 'lucide-react'

/**
 * UserMenu component that displays the current user's information
 * and provides a sign-out button. Follows shadcn/ui sidebar-07 nav-user pattern
 * with dynamic dropdown positioning based on sidebar state.
 */
export default function UserMenu() {
  const { signOut } = useAuth()
  const user = useCurrentUser()
  const { isMobile } = useSidebar()

  const handleSignOut = () => {
    signOut({ returnTo: window.location.origin })
  }

  // Get user initials for avatar fallback (handle edge cases)
  const getInitials = () => {
    // Handle name with trimming and filtering empty parts
    if (user.name?.trim()) {
      const parts = user.name.trim().split(' ').filter(Boolean)
      if (parts.length === 0) return user.email?.[0]?.toUpperCase() || '?'
      return parts.length > 1
        ? `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
        : parts[0][0].toUpperCase()
    }
    return user.email?.[0]?.toUpperCase() || '?'
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <Avatar className="h-8 w-8 rounded-lg">
                <AvatarImage src={user.imageUrl} alt={user.name} />
                <AvatarFallback className="rounded-lg">{getInitials()}</AvatarFallback>
              </Avatar>
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-semibold">{user.name}</span>
                <span className="truncate text-xs">{user.email}</span>
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-[--radix-dropdown-menu-trigger-width] min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                <Avatar className="h-8 w-8 rounded-lg">
                  <AvatarImage src={user.imageUrl} alt={user.name} />
                  <AvatarFallback className="rounded-lg">{getInitials()}</AvatarFallback>
                </Avatar>
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-semibold">{user.name}</span>
                  <span className="truncate text-xs">{user.email}</span>
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleSignOut}>
              <LogOut />
              Sign Out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}
