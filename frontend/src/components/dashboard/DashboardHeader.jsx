import { SidebarTrigger } from "@/components/ui/sidebar"

/**
 * DashboardHeader - Top header bar for the dashboard.
 * Contains the sidebar toggle trigger and breadcrumb/context info.
 */
export default function DashboardHeader() {
  return (
    <header className="flex h-14 shrink-0 items-center border-b px-4">
      <SidebarTrigger className="-ml-1" />
      <div className="flex-1">
        {/* Breadcrumb or page title can go here */}
      </div>
    </header>
  )
}

