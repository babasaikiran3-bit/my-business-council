import { SidebarTrigger } from "@/components/ui/sidebar"
import GlobalSearch from "@/components/GlobalSearch"

/**
 * DashboardHeader - Top header bar for the dashboard.
 * Contains the sidebar toggle trigger, global search bar, and context info.
 *
 * @param {Object} props
 * @param {function} props.onNavigate - Callback to navigate to a feature with optional params
 */
export default function DashboardHeader({ onNavigate }) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b px-4">
      {/* Left: Sidebar trigger */}
      <SidebarTrigger className="-ml-1" />

      {/* Center: Global search bar */}
      <div className="flex-1 flex justify-center">
        <GlobalSearch onNavigate={onNavigate} />
      </div>

      {/* Right: Reserved for future actions (notifications, etc.) */}
      <div className="w-10" />
    </header>
  )
}

