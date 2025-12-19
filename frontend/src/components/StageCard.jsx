/**
 * StageCard - A reusable wrapper for deliberation stage displays.
 * Provides consistent header styling with timing display.
 */

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { CheckCircle2, Clock } from "lucide-react"
import { formatTime, cn } from "@/lib/utils"

/**
 * StageCard - Consistent card wrapper for all deliberation stages.
 *
 * @param {Object} props
 * @param {string} props.title - Stage title (e.g., "Stage 1: Individual Responses")
 * @param {string} props.description - Stage description text
 * @param {Object} props.timing - Timing object with { elapsed, completed } properties
 * @param {React.ReactNode} props.children - Stage content
 * @param {string} props.className - Additional classes for the Card wrapper
 * @param {boolean} props.highlighted - Whether to use highlighted background (for final stage)
 * @param {React.ReactNode} props.icon - Optional custom icon (defaults to CheckCircle2)
 * @param {string} props.iconClassName - Optional icon className (defaults to text-green-500)
 */
export default function StageCard({
  title,
  description,
  timing,
  children,
  className,
  highlighted = false,
  icon,
  iconClassName = "text-green-500",
}) {
  const Icon = icon || CheckCircle2

  return (
    <Card className={cn(highlighted && "bg-muted/30", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Icon className={cn("h-4 w-4", iconClassName)} />
            <CardTitle className="text-sm font-medium">
              {title}
            </CardTitle>
          </div>
          {timing && timing.elapsed > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              <span className="font-mono">Completed in {formatTime(timing.elapsed)}</span>
            </div>
          )}
        </div>
        {description && (
          <CardDescription className="text-xs">
            {description}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent>
        {children}
      </CardContent>
    </Card>
  )
}

/**
 * StageCardDescription - For use when description needs custom styling/content.
 * Use as a child of StageCard when you need more control over the description.
 *
 * @reserved This component is currently unused but reserved for future use cases
 * where stage descriptions need custom React components (e.g., interactive elements,
 * conditional formatting, or rich content beyond simple text strings).
 *
 * @example
 * // Future use case: description with a link
 * <StageCard title="Stage 1">
 *   <StageCardDescription>
 *     View <a href="/docs">documentation</a> for more info.
 *   </StageCardDescription>
 *   {children}
 * </StageCard>
 */
export function StageCardDescription({ children, className }) {
  return (
    <CardDescription className={cn("text-xs", className)}>
      {children}
    </CardDescription>
  )
}

