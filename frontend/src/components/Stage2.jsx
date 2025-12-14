import ReactMarkdown from 'react-markdown';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"
import { CheckCircle2, Clock } from "lucide-react"

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;
  let result = text;
  Object.entries(labelToModel).forEach(([label, model]) => {
    const modelShortName = model.split('/')[1] || model;
    result = result.replace(new RegExp(label, 'g'), `**${modelShortName}**`);
  });
  return result;
}

/**
 * Format elapsed time in seconds with 1 decimal place
 */
function formatTime(ms) {
  if (!ms || ms <= 0) return "0.0s";
  return `${(ms / 1000).toFixed(1)}s`;
}

export default function Stage2({ rankings, labelToModel, aggregateRankings, timing }) {
  if (!rankings || rankings.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-green-500" />
            <CardTitle className="text-sm font-medium">Stage 2: Peer Rankings</CardTitle>
          </div>
          {timing && timing.elapsed > 0 && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              <span className="font-mono">Completed in {formatTime(timing.elapsed)}</span>
            </div>
          )}
        </div>
        <CardDescription className="text-xs">
          {rankings.length} models evaluated responses anonymously. Model names shown in bold for readability.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div>
          <h4 className="text-sm font-medium mb-2">Raw Evaluations</h4>
          <Tabs defaultValue="0" className="w-full">
            <TabsList className="mb-3 flex-wrap h-auto">
              {rankings.map((rank, index) => (
                <TabsTrigger key={index} value={String(index)} className="text-xs">
                  {rank.model.split('/')[1] || rank.model}
                </TabsTrigger>
              ))}
            </TabsList>

            {rankings.map((rank, index) => (
              <TabsContent key={index} value={String(index)}>
                <div className="text-xs text-muted-foreground mb-2 font-mono">
                  {rank.model}
                </div>
                <div className="max-h-96 overflow-y-auto rounded-md border">
                  <div className="markdown-content p-3 bg-muted/50">
                    <ReactMarkdown>
                      {deAnonymizeText(rank.ranking, labelToModel)}
                    </ReactMarkdown>
                  </div>
                </div>

                {rank.parsed_ranking && rank.parsed_ranking.length > 0 && (
                  <div className="mt-3 p-3 bg-muted/30 rounded-md">
                    <div className="text-sm font-medium mb-2">Extracted Ranking:</div>
                    <ol className="list-decimal list-inside space-y-1 text-sm">
                      {rank.parsed_ranking.map((label, i) => (
                        <li key={i} className="text-muted-foreground">
                          {labelToModel && labelToModel[label]
                            ? labelToModel[label].split('/')[1] || labelToModel[label]
                            : label}
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
              </TabsContent>
            ))}
          </Tabs>
        </div>

        {aggregateRankings && aggregateRankings.length > 0 && (
          <div className="border-t pt-4">
            <h4 className="text-sm font-medium mb-2">Aggregate Rankings</h4>
            <p className="text-xs text-muted-foreground mb-3">
              Combined results (lower score is better):
            </p>
            <div className="space-y-2">
              {aggregateRankings.map((agg, index) => (
                <div
                  key={index}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2 rounded-md text-sm",
                    index === 0 ? "bg-muted" : "bg-muted/30"
                  )}
                >
                  <span className={cn(
                    "w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium shrink-0",
                    index === 0 ? "bg-foreground text-background" : "bg-muted-foreground/20 text-muted-foreground"
                  )}>
                    {index + 1}
                  </span>
                  <span className="flex-1 font-medium">
                    {agg.model.split('/')[1] || agg.model}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Avg: {agg.average_rank.toFixed(2)} ({agg.rankings_count} votes)
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
