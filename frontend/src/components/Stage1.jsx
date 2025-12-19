import ReactMarkdown from 'react-markdown';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Clock } from "lucide-react"
import { getModelDisplayName, formatTime } from "@/lib/utils"
import StageCard from './StageCard'

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

  const description = `${successCount}/${totalCount} models responded successfully${failedCount > 0 ? ` • ${failedCount} failed` : ''}`

  return (
    <StageCard
      title="Stage 1: Individual Responses"
      description={description}
      timing={timing}
    >
      <Tabs defaultValue="0" className="w-full">
        <TabsList className="mb-3 flex-wrap h-auto">
          {responses.map((resp, index) => (
            <TabsTrigger key={index} value={String(index)} className="text-xs">
              {getModelDisplayName(resp.model)}
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
    </StageCard>
  );
}
