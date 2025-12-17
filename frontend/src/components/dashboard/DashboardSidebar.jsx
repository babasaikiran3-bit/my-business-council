"use client"

import * as React from "react"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarRail,
  useSidebar,
} from "@/components/ui/sidebar"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  LayoutDashboard,
  BarChart3,
  Settings,
  Users,
  FileText,
  Workflow,
  Shield,
  Bot,
  ChevronRight,
} from "lucide-react"
import UserMenu from "../UserMenu"

// Logo images for sidebar header
const logoFull = "/logo-full.png"
const logoMark = "/logo-mark.png"

/**
 * Navigation items for the dashboard grouped by section.
 *
 * Each item can optionally have a `subItems` array for collapsible sub-menus.
 * Structure:
 * - id: unique identifier for navigation
 * - label: display text
 * - icon: Lucide icon component
 * - disabled?: boolean to disable the item
 * - badge?: string to show a badge (e.g., "Soon")
 * - isActive?: boolean to set default expanded state for items with subItems
 * - subItems?: array of { id, label } for collapsible sub-menu items
 */
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
      {
        id: "workflows",
        label: "Workflows",
        icon: Workflow,
        badge: "Soon",
        subItems: [
          { id: "workflows-builder", label: "Workflow Builder" },
          { id: "workflows-templates", label: "Templates" },
          { id: "workflows-history", label: "Run History" },
        ]
      },
    ]
  },
  {
    group: "Analytics",
    items: [
      {
        id: "analytics",
        label: "Analytics",
        icon: BarChart3,
        badge: "Soon",
        subItems: [
          { id: "analytics-overview", label: "Overview" },
          { id: "analytics-usage", label: "Usage Metrics" },
          { id: "analytics-performance", label: "Performance" },
          { id: "analytics-costs", label: "Cost Analysis" },
        ]
      },
      {
        id: "reports",
        label: "Reports",
        icon: FileText,
        badge: "Soon",
        subItems: [
          { id: "reports-scheduled", label: "Scheduled Reports" },
          { id: "reports-custom", label: "Custom Reports" },
          { id: "reports-exports", label: "Exports" },
        ]
      },
    ]
  },
  {
    group: "Administration",
    items: [
      {
        id: "team",
        label: "Team",
        icon: Users,
        badge: "Soon",
        subItems: [
          { id: "team-members", label: "Members" },
          { id: "team-roles", label: "Roles & Permissions" },
          { id: "team-invitations", label: "Invitations" },
        ]
      },
      {
        id: "security",
        label: "Security",
        icon: Shield,
        badge: "Soon",
        subItems: [
          { id: "security-audit", label: "Audit Log" },
          { id: "security-sessions", label: "Active Sessions" },
          { id: "security-api-keys", label: "API Keys" },
          { id: "security-sso", label: "SSO Configuration" },
        ]
      },
      {
        id: "settings",
        label: "Settings",
        icon: Settings,
        badge: "Soon",
        isActive: true, // Default open to demonstrate expanded state
        subItems: [
          { id: "settings-general", label: "General" },
          { id: "settings-notifications", label: "Notifications" },
          { id: "settings-integrations", label: "Integrations" },
          { id: "settings-billing", label: "Billing" },
        ]
      },
    ]
  },
]

/**
 * NavMain - Navigation groups component following sidebar-07 pattern.
 *
 * Supports two types of navigation items:
 * 1. Flat items: Direct click navigation (no subItems)
 * 2. Collapsible items: Expandable with sub-menu items (has subItems array)
 *
 * The component automatically detects which pattern to use based on the
 * presence of the `subItems` property in each navigation item.
 */
function NavMain({ items, activeFeature, onFeatureChange }) {
  return (
    <>
      {items.map((group) => (
        <SidebarGroup key={group.group}>
          <SidebarGroupLabel>{group.group}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {group.items.map((item) => {
                // Check if item has sub-items for collapsible behavior
                const hasSubItems = item.subItems && item.subItems.length > 0

                if (hasSubItems) {
                  // Collapsible menu item with sub-items (sidebar-07 pattern)
                  return (
                    <Collapsible
                      key={item.id}
                      asChild
                      defaultOpen={item.isActive}
                      className="group/collapsible"
                    >
                      <SidebarMenuItem>
                        <CollapsibleTrigger asChild>
                          <SidebarMenuButton
                            tooltip={item.label}
                            disabled={item.disabled}
                            className={item.disabled ? "opacity-50 cursor-not-allowed" : ""}
                          >
                            <item.icon />
                            <span>{item.label}</span>
                            {item.badge && (
                              <span className="ml-auto text-xs text-muted-foreground">
                                {item.badge}
                              </span>
                            )}
                            <ChevronRight className={`${item.badge ? "ml-2" : "ml-auto"} transition-transform duration-200 group-data-[state=open]/collapsible:rotate-90`} />
                          </SidebarMenuButton>
                        </CollapsibleTrigger>
                        <CollapsibleContent>
                          <SidebarMenuSub>
                            {item.subItems.map((subItem) => (
                              <SidebarMenuSubItem key={subItem.id}>
                                <SidebarMenuSubButton
                                  isActive={activeFeature === subItem.id}
                                  onClick={() => !item.badge && onFeatureChange(subItem.id)}
                                  className={item.badge ? "opacity-50 cursor-not-allowed" : ""}
                                >
                                  <span>{subItem.label}</span>
                                </SidebarMenuSubButton>
                              </SidebarMenuSubItem>
                            ))}
                          </SidebarMenuSub>
                        </CollapsibleContent>
                      </SidebarMenuItem>
                    </Collapsible>
                  )
                }

                // Flat menu item without sub-items (direct navigation)
                return (
                  <SidebarMenuItem key={item.id}>
                    <SidebarMenuButton
                      isActive={activeFeature === item.id}
                      onClick={() => !item.disabled && onFeatureChange(item.id)}
                      disabled={item.disabled}
                      tooltip={item.label}
                      className={item.disabled ? "opacity-50 cursor-not-allowed" : ""}
                    >
                      <item.icon />
                      <span>{item.label}</span>
                    </SidebarMenuButton>
                    {item.badge && (
                      <SidebarMenuBadge>{item.badge}</SidebarMenuBadge>
                    )}
                  </SidebarMenuItem>
                )
              })}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      ))}
    </>
  )
}

/**
 * LogoSwitcher - Header component that switches between full and icon logos.
 * Uses SidebarMenuButton with size="lg" following sidebar-07 pattern.
 */
function LogoSwitcher() {
  const { state } = useSidebar()

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <SidebarMenuButton
          size="lg"
          className="hover:bg-transparent active:bg-transparent cursor-default"
        >
          {state === "expanded" ? (
            <img
              src={logoFull}
              alt="Eternal"
              className="h-13 w-auto object-contain"
            />
          ) : (
            <div className="flex aspect-square size-8 items-center justify-center">
              <img
                src={logoMark}
                alt="Eternal"
                className="size-8 object-contain"
              />
            </div>
          )}
        </SidebarMenuButton>
      </SidebarMenuItem>
    </SidebarMenu>
  )
}

/**
 * DashboardSidebar - Navigation sidebar for Eternal Ops Control.
 * Follows the shadcn/ui sidebar-07 pattern with collapsible icon mode.
 *
 * @param {Object} props
 * @param {string} props.activeFeature - Currently active feature id
 * @param {Function} props.onFeatureChange - Callback when feature selection changes
 */
export default function DashboardSidebar({ activeFeature, onFeatureChange }) {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <LogoSwitcher />
      </SidebarHeader>

      <SidebarContent>
        <NavMain
          items={NAV_ITEMS}
          activeFeature={activeFeature}
          onFeatureChange={onFeatureChange}
        />
      </SidebarContent>

      <SidebarFooter>
        <UserMenu />
      </SidebarFooter>

      <SidebarRail />
    </Sidebar>
  )
}

