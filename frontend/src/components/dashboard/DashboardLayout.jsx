import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar"
import DashboardSidebar from "./DashboardSidebar"
import DashboardHeader from "./DashboardHeader"

/**
 * DashboardLayout - Main layout wrapper for the Eternal Ops Control dashboard.
 * Uses shadcn/ui sidebar components for responsive navigation.
 * 
 * @param {Object} props
 * @param {string} props.activeFeature - The currently active feature/route
 * @param {Function} props.onFeatureChange - Callback when feature selection changes
 * @param {React.ReactNode} props.children - The main content to display
 */
export default function DashboardLayout({ 
  activeFeature, 
  onFeatureChange, 
  children 
}) {
  return (
    <SidebarProvider defaultOpen={true}>
      <DashboardSidebar 
        activeFeature={activeFeature} 
        onFeatureChange={onFeatureChange} 
      />
      <SidebarInset>
        <DashboardHeader />
        <main className="flex-1 overflow-hidden">
          {children}
        </main>
      </SidebarInset>
    </SidebarProvider>
  )
}

