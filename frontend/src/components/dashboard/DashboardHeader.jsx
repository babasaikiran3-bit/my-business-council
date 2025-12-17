import { SidebarTrigger } from "@/components/ui/sidebar"
import { Separator } from "@/components/ui/separator"

/**
 * DashboardHeader - Top header bar for the dashboard.
 * Contains the sidebar toggle trigger and breadcrumb/context info.
 */
export default function DashboardHeader() {
  return (
    <header className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mr-2 h-4" />
      <div className="flex-1">
        {/* Breadcrumb or page title can go here */}
      </div>
    </header>
  )
}

