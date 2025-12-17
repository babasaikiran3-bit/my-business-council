import { useState, useEffect, useCallback, useRef } from "react"
import { Button } from "@/components/ui/button"
import { PlusCircle, MessageSquare, GripVertical, Loader2, Square } from "lucide-react"
import { cn } from "@/lib/utils"

const SIDEBAR_MIN_WIDTH = 240;
const SIDEBAR_MAX_WIDTH = 480;
const SIDEBAR_DEFAULT_WIDTH = 288; // w-72
const STORAGE_KEY = 'eternal-ops-sidebar-width';

/**
 * Format a timestamp into a human-readable relative or absolute format.
 * Returns relative time for recent timestamps, absolute date for older ones.
 */
function formatTimestamp(isoString) {
  if (!isoString) return null;

  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return null;

    const now = new Date();
    const diffMs = now - date;
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    // Less than 1 minute ago
    if (diffSec < 60) {
      return 'Just now';
    }

    // Less than 1 hour ago
    if (diffMin < 60) {
      return `${diffMin} minute${diffMin === 1 ? '' : 's'} ago`;
    }

    // Less than 24 hours ago
    if (diffHour < 24) {
      return `${diffHour} hour${diffHour === 1 ? '' : 's'} ago`;
    }

    // Yesterday
    if (diffDay === 1) {
      return 'Yesterday';
    }

    // Less than 7 days ago
    if (diffDay < 7) {
      return `${diffDay} days ago`;
    }

    // Older than 7 days - show absolute date
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
    });
  } catch {
    return null;
  }
}

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  userMenu,
  processingConversations = new Map(), // Map of conversation IDs that are currently processing
  onCancelStream, // Handler to cancel stream for a specific conversation
}) {
  const [width, setWidth] = useState(SIDEBAR_DEFAULT_WIDTH);
  const [isResizing, setIsResizing] = useState(false);
  const sidebarRef = useRef(null);

  // Load saved width from localStorage on mount
  useEffect(() => {
    const savedWidth = localStorage.getItem(STORAGE_KEY);
    if (savedWidth) {
      const parsed = parseInt(savedWidth, 10);
      if (!isNaN(parsed) && parsed >= SIDEBAR_MIN_WIDTH && parsed <= SIDEBAR_MAX_WIDTH) {
        setWidth(parsed);
      }
    }
  }, []);

  // Save width to localStorage when it changes
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(width));
  }, [width]);

  const startResizing = useCallback((e) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  const stopResizing = useCallback(() => {
    setIsResizing(false);
  }, []);

  const resize = useCallback((e) => {
    if (!isResizing || !sidebarRef.current) return;

    const newWidth = e.clientX - sidebarRef.current.getBoundingClientRect().left;
    const clampedWidth = Math.min(Math.max(newWidth, SIDEBAR_MIN_WIDTH), SIDEBAR_MAX_WIDTH);
    setWidth(clampedWidth);
  }, [isResizing]);

  // Add/remove event listeners for resize
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', resize);
      document.addEventListener('mouseup', stopResizing);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', resize);
      document.removeEventListener('mouseup', stopResizing);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing, resize, stopResizing]);

  return (
    <div
      ref={sidebarRef}
      className="bg-muted/40 border-r flex flex-col h-full relative shrink-0 overflow-hidden"
      style={{ width: `${width}px` }}
    >
      {/* Header section with increased horizontal padding */}
      <div className="px-14 py-8 border-b space-y-8 shrink-0">
        <h1 className="text-xl font-semibold text-foreground">Eternal Ops Control</h1>
        <Button className="w-full h-10" onClick={onNewConversation}>
          <PlusCircle className="h-4 w-4 mr-2" />
          New Conversation
        </Button>
      </div>

      {/* Conversation list - using native scrolling for reliability */}
      {/* flex-1 min-h-0 pattern: flex-1 fills space, min-h-0 allows shrinking below content size, overflow-y-auto enables scrolling */}
      <div className="flex-1 min-h-0 overflow-y-auto">
        <div className="px-12 pt-5 pb-4">
          {conversations.length === 0 ? (
            <div className="p-6 text-center text-muted-foreground text-sm">
              No conversations yet
            </div>
          ) : (
            <div className="space-y-3">
              {conversations.map((conv) => {
                const timestamp = formatTimestamp(conv.created_at);
                const isProcessing = processingConversations.has(conv.id);
                return (
                  <button
                    key={conv.id}
                    className={cn(
                      "w-full text-left px-4 py-3 rounded-lg text-sm transition-colors",
                      "hover:bg-accent",
                      conv.id === currentConversationId
                        ? "bg-accent text-accent-foreground"
                        : "text-muted-foreground"
                    )}
                    onClick={() => onSelectConversation(conv.id)}
                  >
                    <div className="flex items-start gap-3">
                      {isProcessing ? (
                        <Loader2 className="h-4 w-4 mt-0.5 shrink-0 animate-spin text-primary" />
                      ) : (
                        <MessageSquare className="h-4 w-4 mt-0.5 shrink-0" />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="font-medium truncate">
                          {conv.title || 'New Conversation'}
                        </div>
                        <div className="text-xs text-muted-foreground/70 mt-1 flex items-center gap-2">
                          {isProcessing ? (
                            <span className="text-primary">Processing...</span>
                          ) : (
                            <>
                              <span>{conv.message_count} messages</span>
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
                      {/* Stop button for processing conversations */}
                      {isProcessing && onCancelStream && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation()
                            onCancelStream(conv.id)
                          }}
                          className={cn(
                            'p-1 rounded hover:bg-destructive/10 transition-colors',
                            'text-destructive hover:text-destructive',
                            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
                          )}
                          title="Stop processing"
                        >
                          <Square className="h-3.5 w-3.5 fill-current" />
                        </button>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* User menu at the bottom - shrink-0 ensures it doesn't shrink when scroll area fills */}
      <div className="shrink-0">
        {userMenu}
      </div>

      {/* Resize handle */}
      <div
        className={cn(
          "absolute top-0 right-0 w-1 h-full cursor-col-resize group",
          "hover:bg-primary/20 transition-colors",
          isResizing && "bg-primary/30"
        )}
        onMouseDown={startResizing}
      >
        {/* Grip indicator */}
        <div className={cn(
          "absolute top-1/2 -translate-y-1/2 -translate-x-1/2 left-1/2",
          "opacity-0 group-hover:opacity-100 transition-opacity",
          isResizing && "opacity-100"
        )}>
          <GripVertical className="h-6 w-6 text-muted-foreground" />
        </div>
      </div>
    </div>
  );
}
