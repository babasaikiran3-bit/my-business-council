import ReactMarkdown from 'react-markdown';
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn, getModelDisplayName } from "@/lib/utils"
import StageCard from './StageCard'

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;
  let result = text;
  Object.entries(labelToModel).forEach(([label, model]) => {
    const modelShortName = getModelDisplayName(model);
    result = result.replace(new RegExp(label, 'g'), `**${modelShortName}**`);
  });
  return result;
}

export default function Stage2({ rankings, labelToModel, aggregateRankings, timing }) {
  if (!rankings || rankings.length === 0) {
    return null;
  }

  const description = `${rankings.length} models evaluated responses anonymously. Model names shown in bold for readability.`

  return (
    <StageCard
      title="Stage 2: Peer Rankings"
      description={description}
      timing={timing}
    >
      <div className="space-y-4">
        <div>
          <h4 className="text-sm font-medium mb-2">Raw Evaluations</h4>
          <Tabs defaultValue="0" className="w-full">
            <TabsList className="mb-3 flex-wrap h-auto">
              {rankings.map((rank, index) => (
                <TabsTrigger key={index} value={String(index)} className="text-xs">
                  {getModelDisplayName(rank.model)}
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
                            ? getModelDisplayName(labelToModel[label])
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
                    {getModelDisplayName(agg.model)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    Avg: {agg.average_rank.toFixed(2)} ({agg.rankings_count} votes)
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </StageCard>
  );
}
