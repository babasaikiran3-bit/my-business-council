import ReactMarkdown from 'react-markdown';
import StageCard from './StageCard'
import { getModelDisplayName } from "@/lib/utils"

export default function Stage3({ finalResponse, timing }) {
  if (!finalResponse) {
    return null;
  }

  return (
    <StageCard
      title="Stage 3: Final Copilot Answer"
      description={<span className="font-mono">Chairman: {getModelDisplayName(finalResponse.model)}</span>}
      timing={timing}
      highlighted
    >
      <div className="markdown-content">
        {finalResponse.response ? (
          <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
        ) : (
          <p className="text-muted-foreground italic">
            No response generated. This may happen if the combined context from Stage 1 and Stage 2 exceeded the model&apos;s context limit.
          </p>
        )}
      </div>
    </StageCard>
  );
}
