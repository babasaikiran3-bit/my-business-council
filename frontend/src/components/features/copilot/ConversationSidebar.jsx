import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { PlusCircle, MessageSquare, Loader2 } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Format a timestamp into a human-readable relative or absolute format.
 */
function formatTimestamp(isoString) {
  if (!isoString) return null

  try {
    const date = new Date(isoString)
    if (isNaN(date.getTime())) return null

    const now = new Date()
    const diffMs = now - date
    const diffSec = Math.floor(diffMs / 1000)
    const diffMin = Math.floor(diffSec / 60)
    const diffHour = Math.floor(diffMin / 60)
    const diffDay = Math.floor(diffHour / 24)

    if (diffSec < 60) return 'Just now'
    if (diffMin < 60) return `${diffMin} minute${diffMin === 1 ? '' : 's'} ago`
    if (diffHour < 24) return `${diffHour} hour${diffHour === 1 ? '' : 's'} ago`
    if (diffDay === 1) return 'Yesterday'
    if (diffDay < 7) return `${diffDay} days ago`

    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
    })
  } catch {
    return null
  }
}

/**
 * ConversationSidebar - Secondary sidebar for managing Copilot conversations.
 * Displays within the main content area of the dashboard.
 */
export default function ConversationSidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  processingConversations = new Map(),
}) {
  return (
    <div className="w-64 border-r bg-muted/30 flex flex-col h-full shrink-0">
      {/* Header */}
      <div className="p-4 border-b space-y-3">
        <h2 className="text-sm font-medium text-muted-foreground">Conversations</h2>
        <Button className="w-full h-9" size="sm" onClick={onNewConversation}>
          <PlusCircle className="h-4 w-4 mr-2" />
          New Conversation
        </Button>
      </div>

      {/* Conversation list */}
      <ScrollArea className="flex-1">
        <div className="p-2">
          {conversations.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground text-sm">
              No conversations yet
            </div>
          ) : (
            <div className="space-y-1">
              {conversations.map((conv) => {
                const timestamp = formatTimestamp(conv.created_at)
                const isProcessing = processingConversations.has(conv.id)
                return (
                  <button
                    key={conv.id}
                    className={cn(
                      "w-full text-left px-3 py-2 rounded-md text-sm transition-colors",
                      "hover:bg-accent",
                      conv.id === currentConversationId
                        ? "bg-accent text-accent-foreground"
                        : "text-muted-foreground"
                    )}
                    onClick={() => onSelectConversation(conv.id)}
                  >
                    <div className="flex items-start gap-2">
                      {isProcessing ? (
                        <Loader2 className="h-4 w-4 mt-0.5 shrink-0 animate-spin text-primary" />
                      ) : (
                        <MessageSquare className="h-4 w-4 mt-0.5 shrink-0" />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="font-medium truncate text-xs">
                          {conv.title || 'New Conversation'}
                        </div>
                        <div className="text-xs text-muted-foreground/70 mt-0.5 flex items-center gap-1">
                          {isProcessing ? (
                            <span className="text-primary">Processing...</span>
                          ) : (
                            <>
                              <span>{conv.message_count} msgs</span>
                              {timestamp && (
                                <>
                                  <span className="text-muted-foreground/40">•</span>
                                  <span>{timestamp}</span>
                                </>
                              )}
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  )
}

