import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Construction } from "lucide-react"

/**
 * PlaceholderFeature - Generic placeholder for features that are coming soon.
 */
export default function PlaceholderFeature({ 
  title = "Feature", 
  description = "This feature is coming soon." 
}) {
  return (
    <div className="flex items-center justify-center h-full p-6">
      <Card className="max-w-md text-center">
        <CardHeader>
          <div className="mx-auto mb-4 h-12 w-12 rounded-full bg-muted flex items-center justify-center">
            <Construction className="h-6 w-6 text-muted-foreground" />
          </div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            We're working hard to bring you this feature. Check back soon!
          </p>
        </CardContent>
      </Card>
    </div>
  )
}

