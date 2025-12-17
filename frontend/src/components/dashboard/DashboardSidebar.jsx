import { 
  Sidebar, 
  SidebarContent, 
  SidebarFooter, 
  SidebarGroup, 
  SidebarGroupContent, 
  SidebarGroupLabel, 
  SidebarHeader, 
  SidebarMenu, 
  SidebarMenuButton, 
  SidebarMenuItem,
  SidebarRail,
} from "@/components/ui/sidebar"
import { 
  Bot, 
  LayoutDashboard, 
  BarChart3, 
  Settings, 
  Users,
  FileText,
  Workflow,
  Shield,
} from "lucide-react"
import UserMenu from "../UserMenu"

// Navigation items for the dashboard
const NAV_ITEMS = [
  {
    group: "Overview",
    items: [
      { id: "home", label: "Dashboard", icon: LayoutDashboard },
    ]
  },
  {
    group: "AI Tools",
    items: [
      { id: "copilot", label: "Copilot", icon: Bot },
      { id: "workflows", label: "Workflows", icon: Workflow, disabled: true, badge: "Soon" },
    ]
  },
  {
    group: "Analytics",
    items: [
      { id: "analytics", label: "Analytics", icon: BarChart3, disabled: true, badge: "Soon" },
      { id: "reports", label: "Reports", icon: FileText, disabled: true, badge: "Soon" },
    ]
  },
  {
    group: "Administration",
    items: [
      { id: "team", label: "Team", icon: Users, disabled: true, badge: "Soon" },
      { id: "security", label: "Security", icon: Shield, disabled: true, badge: "Soon" },
      { id: "settings", label: "Settings", icon: Settings, disabled: true, badge: "Soon" },
    ]
  },
]

/**
 * DashboardSidebar - Navigation sidebar for Eternal Ops Control.
 * Uses shadcn/ui Sidebar components for collapsible, responsive navigation.
 */
export default function DashboardSidebar({ activeFeature, onFeatureChange }) {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="border-b border-sidebar-border">
        <div className="flex items-center gap-2 px-2 py-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Bot className="h-4 w-4" />
          </div>
          <div className="flex flex-col group-data-[collapsible=icon]:hidden">
            <span className="text-sm font-semibold">Eternal Ops Control</span>
            <span className="text-xs text-muted-foreground">Operations Platform</span>
          </div>
        </div>
      </SidebarHeader>
      
      <SidebarContent>
        {NAV_ITEMS.map((group) => (
          <SidebarGroup key={group.group}>
            <SidebarGroupLabel>{group.group}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {group.items.map((item) => (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton
                      isActive={activeFeature === item.id}
                      onClick={() => !item.disabled && onFeatureChange(item.id)}
                      disabled={item.disabled}
                      tooltip={item.label}
                      className={item.disabled ? "opacity-50 cursor-not-allowed" : ""}
                    >
                      <item.icon className="h-4 w-4" />
                      <span>{item.label}</span>
                      {item.badge && (
                        <span className="ml-auto text-xs bg-muted text-muted-foreground px-1.5 py-0.5 rounded">
                          {item.badge}
                        </span>
                      )}
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
        <UserMenu />
      </SidebarFooter>
      
      <SidebarRail />
    </Sidebar>
  )
}

