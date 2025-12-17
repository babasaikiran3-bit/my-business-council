import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Bot, BarChart3, Users, FileText, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"

/**
 * HomeFeature - Dashboard home page with overview cards and quick actions.
 */
export default function HomeFeature({ onNavigate }) {
  const quickActions = [
    {
      id: 'copilot',
      title: 'LLM Copilot',
      description: '3-stage AI deliberation system for complex queries',
      icon: Bot,
      status: 'active',
    },
    {
      id: 'analytics',
      title: 'Analytics',
      description: 'Monitor AI usage and performance metrics',
      icon: BarChart3,
      status: 'coming-soon',
    },
    {
      id: 'team',
      title: 'Team Management',
      description: 'Manage team members and permissions',
      icon: Users,
      status: 'coming-soon',
    },
    {
      id: 'reports',
      title: 'Reports',
      description: 'Generate and export operational reports',
      icon: FileText,
      status: 'coming-soon',
    },
  ]

  return (
    <div className="p-6 space-y-6 overflow-auto h-full">
      {/* Welcome section */}
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">Welcome to Eternal Ops Control</h1>
        <p className="text-muted-foreground">
          Your unified operations platform for AI-powered workflows and team management.
        </p>
      </div>

      {/* Quick actions grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {quickActions.map((action) => (
          <Card 
            key={action.id} 
            className={action.status === 'active' ? 'cursor-pointer hover:border-primary/50 transition-colors' : 'opacity-60'}
            onClick={() => action.status === 'active' && onNavigate(action.id)}
          >
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                {action.title}
              </CardTitle>
              <action.icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground mb-3">
                {action.description}
              </p>
              {action.status === 'active' ? (
                <Button variant="ghost" size="sm" className="p-0 h-auto text-xs">
                  Open <ArrowRight className="h-3 w-3 ml-1" />
                </Button>
              ) : (
                <span className="text-xs text-muted-foreground/60 italic">Coming soon</span>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Stats section placeholder */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Conversations</CardDescription>
            <CardTitle className="text-3xl">—</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">Stats coming soon</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>AI Queries This Week</CardDescription>
            <CardTitle className="text-3xl">—</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">Stats coming soon</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Active Team Members</CardDescription>
            <CardTitle className="text-3xl">—</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground">Stats coming soon</p>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

