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
  LayoutDashboard,
  BarChart3,
  Settings,
  Users,
  FileText,
  Workflow,
  Shield,
  Bot,
} from "lucide-react"
import UserMenu from "../UserMenu"

// Logo images for sidebar header
const logoFull = "/logo-full.png"
const logoMark = "/logo-mark.png"

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
      <SidebarHeader className="h-14 border-b border-sidebar-border">
        <div className="flex h-full w-full items-center justify-center px-3 group-data-[collapsible=icon]:px-0">
          {/* Full logo - shown when sidebar is expanded */}
          <img
            src={logoFull}
            alt="Eternal"
            className="h-[52px] w-auto object-contain group-data-[collapsible=icon]:hidden"
          />
          {/* Mark/icon logo - shown when sidebar is collapsed */}
          <img
            src={logoMark}
            alt="Eternal"
            className="h-10 w-10 object-contain hidden group-data-[collapsible=icon]:block"
          />
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

