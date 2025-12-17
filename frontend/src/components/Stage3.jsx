import ReactMarkdown from 'react-markdown';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { CheckCircle2, Clock } from "lucide-react"
import { getModelDisplayName } from "@/lib/utils"

/**
 * Format elapsed time in seconds with 1 decimal place
 */
function formatTime(ms) {
  if (!ms || ms <= 0) return "0.0s";
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function Stage3({ finalResponse, timing }) {
  if (!finalResponse) {
    return null;
  }

  return (
    <Card className="bg-muted/30">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-green-500" />
            <CardTitle className="text-sm font-medium">Stage 3: Final Copilot Answer</CardTitle>
          </div>
          {timing && timing.elapsed > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              <span className="font-mono">Completed in {formatTime(timing.elapsed)}</span>
            </div>
          )}
        </div>
        <CardDescription className="text-xs font-mono">
          Chairman: {getModelDisplayName(finalResponse.model)}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="markdown-content">
          <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
        </div>
      </CardContent>
    </Card>
  );
}
