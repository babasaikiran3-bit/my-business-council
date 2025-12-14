import ReactMarkdown from 'react-markdown';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { CheckCircle2, Clock } from "lucide-react"

/**
 * Format elapsed time in seconds with 1 decimal place
 */
function formatTime(ms) {
  if (!ms || ms <= 0) return "0.0s";
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function Stage1({ responses, timing, modelStatuses, modelTimings }) {
  if (!responses || responses.length === 0) {
    return null;
  }

  // Calculate success/failure counts from modelStatuses or responses
  const successCount = modelStatuses
    ? Object.values(modelStatuses).filter(s => s === 'received').length
    : responses.length;
  const failedCount = modelStatuses
    ? Object.values(modelStatuses).filter(s => s === 'failed').length
    : 0;
  const totalCount = modelStatuses
    ? Object.keys(modelStatuses).length
    : responses.length;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-green-500" />
            <CardTitle className="text-sm font-medium">
              Stage 1: Individual Responses
            </CardTitle>
          </div>
          {timing && timing.elapsed > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              <span className="font-mono">Completed in {formatTime(timing.elapsed)}</span>
            </div>
          )}
        </div>
        <CardDescription className="text-xs">
          {successCount}/{totalCount} models responded successfully
          {failedCount > 0 && ` • ${failedCount} failed`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="0" className="w-full">
          <TabsList className="mb-3 flex-wrap h-auto">
            {responses.map((resp, index) => (
              <TabsTrigger key={index} value={String(index)} className="text-xs">
                {resp.model.split('/')[1] || resp.model}
              </TabsTrigger>
            ))}
          </TabsList>

          {responses.map((resp, index) => {
            const responseTimeMs = modelTimings?.[resp.model];
            return (
              <TabsContent key={index} value={String(index)}>
                <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
                  <span className="font-mono">{resp.model}</span>
                  {responseTimeMs && (
                    <span className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      <span className="font-mono">Responded in {formatTime(responseTimeMs)}</span>
                    </span>
                  )}
                </div>
                <div className="max-h-96 overflow-y-auto rounded-md border">
                  <div className="markdown-content p-3 bg-muted/50">
                    <ReactMarkdown>{resp.response}</ReactMarkdown>
                  </div>
                </div>
              </TabsContent>
            );
          })}
        </Tabs>
      </CardContent>
    </Card>
  );
}
