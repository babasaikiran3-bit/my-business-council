import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { toast } from 'sonner';
import { api } from '../api';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import { Stage1Progress, StageProgress } from './ProgressIndicator';
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import { Sparkles, Send, Undo2, Loader2, User, Users, AlertCircle, RefreshCw, StopCircle } from "lucide-react"
import { cn } from "@/lib/utils"

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  stageTimings,
  modelStatuses,
  modelTimings,
  currentError,
  onRetry,
  onClearError,
  onCancelStream,
}) {
  const [input, setInput] = useState('');
  const [isImproving, setIsImproving] = useState(false);
  const [originalPrompt, setOriginalPrompt] = useState(null);
  const messagesEndRef = useRef(null);
  const scrollAreaRef = useRef(null);
  const prevMessageCountRef = useRef(0);
  const userScrolledUpRef = useRef(false);

  const scrollToBottom = () => {
    // Use scrollTo on the container instead of scrollIntoView to avoid
    // scrolling ancestor containers (which breaks the conversation sidebar scroll)
    const container = scrollAreaRef.current;
    if (container) {
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth'
      });
    }
  };

  // Track if user has scrolled up manually
  const handleScroll = (e) => {
    const viewport = e.target;
    if (!viewport) return;

    const { scrollTop, scrollHeight, clientHeight } = viewport;
    // Consider "near bottom" if within 100px of the bottom
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;
    const wasScrolledUp = userScrolledUpRef.current;
    userScrolledUpRef.current = !isNearBottom;

    // Debug logging
    if (wasScrolledUp !== userScrolledUpRef.current) {
      console.log('[ChatInterface] Scroll state changed:', {
        userScrolledUp: userScrolledUpRef.current,
        scrollTop,
        scrollHeight,
        clientHeight,
        distanceFromBottom: scrollHeight - scrollTop - clientHeight
      });
    }
  };

  // Only auto-scroll when:
  // 1. A new message is added (message count increases)
  // 2. User hasn't manually scrolled up
  useEffect(() => {
    const currentMessageCount = conversation?.messages?.length || 0;
    const prevMessageCount = prevMessageCountRef.current;

    console.log('[ChatInterface] Message count effect:', {
      currentMessageCount,
      prevMessageCount,
      userScrolledUp: userScrolledUpRef.current,
      willScroll: currentMessageCount > prevMessageCount && !userScrolledUpRef.current
    });

    // If a new message was added and user hasn't scrolled up, scroll to bottom
    if (currentMessageCount > prevMessageCount && !userScrolledUpRef.current) {
      scrollToBottom();
    }

    // Update previous count
    prevMessageCountRef.current = currentMessageCount;
  }, [conversation?.messages?.length]);

  // Track if this is the first render for this conversation ID
  const lastSeenConversationIdRef = useRef(null);

  // Reset scroll state when conversation changes (different conversation selected)
  useEffect(() => {
    // Only reset scroll if this is actually a different conversation
    if (conversation?.id !== lastSeenConversationIdRef.current) {
      console.log('[ChatInterface] Conversation ID changed:', {
        from: lastSeenConversationIdRef.current,
        to: conversation?.id
      });
      userScrolledUpRef.current = false;
      prevMessageCountRef.current = conversation?.messages?.length || 0;
      lastSeenConversationIdRef.current = conversation?.id;
      // Scroll to bottom when switching conversations
      scrollToBottom();
    }
  }, [conversation?.id]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading && !isImproving) {
      // Pass originalPrompt if the prompt was improved
      onSendMessage(input, originalPrompt);
      setInput('');
      setOriginalPrompt(null);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleImprovePrompt = async () => {
    if (!input.trim() || isImproving || isLoading) return;
    setIsImproving(true);
    setOriginalPrompt(input);
    try {
      const result = await api.improvePrompt(input);
      setInput(result.improved_prompt);
      toast.success('Prompt improved! Review the changes before sending.');
    } catch (error) {
      console.error('Failed to improve prompt:', error);
      toast.error('Failed to improve prompt. Please try again.');
      setOriginalPrompt(null);
    }
    setIsImproving(false);
  };

  const handleUndoImprovement = () => {
    if (originalPrompt) {
      setInput(originalPrompt);
      setOriginalPrompt(null);
    }
  };

  if (!conversation) {
    return (
      <div className="flex-1 min-h-0 flex items-center justify-center bg-background">
        <div className="text-center">
          <h2 className="text-2xl font-semibold text-foreground mb-2">Welcome to Eternal Copilot</h2>
          <p className="text-muted-foreground">Create a new conversation to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col bg-background flex-1 min-h-0 overflow-hidden">
      {/* Using native scrolling for reliability - flex-1 min-h-0 pattern with overflow-y-auto */}
      <div ref={scrollAreaRef} className="flex-1 min-h-0 overflow-y-auto" onScroll={handleScroll}>
        <div className="p-6">
          {conversation.messages.length === 0 ? (
            <div className="flex items-center justify-center min-h-[calc(100vh-200px)]">
              <div className="text-center">
                <h2 className="text-2xl font-semibold text-foreground mb-2">Start a conversation</h2>
                <p className="text-muted-foreground">Ask a question to consult Eternal Copilot</p>
              </div>
            </div>
          ) : (
            <div className="space-y-6 max-w-4xl mx-auto">
              {conversation.messages.map((msg, index) => (
              <div key={index} className="space-y-4">
                {msg.role === 'user' ? (
                  <Card className="bg-muted/50">
                    <CardContent className="pt-4">
                      <div className="flex items-center gap-2 mb-2 text-sm font-medium">
                        <User className="h-4 w-4" />
                        You
                      </div>
                      <div className="markdown-content">
                        <ReactMarkdown>{msg.content}</ReactMarkdown>
                      </div>
                    </CardContent>
                  </Card>
                ) : (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                        <Users className="h-4 w-4" />
                        Eternal Copilot
                      </div>
                      {isLoading && onCancelStream && (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={onCancelStream}
                          className="h-7 text-destructive border-destructive/50 hover:bg-destructive/10 hover:text-destructive"
                        >
                          <StopCircle className="h-3.5 w-3.5 mr-1.5" />
                          Stop
                        </Button>
                      )}
                    </div>

                    {msg.loading?.stage1 && Object.keys(modelStatuses).length > 0 && (
                      <Stage1Progress
                        modelStatuses={modelStatuses}
                        timing={stageTimings.stage1}
                        onCancel={onCancelStream}
                      />
                    )}
                    {msg.loading?.stage1 && Object.keys(modelStatuses).length === 0 && (
                      <StageProgress
                        stage={1}
                        label="Stage 1: Collecting responses..."
                        timing={stageTimings.stage1}
                        onCancel={onCancelStream}
                      />
                    )}
                    {msg.stage1 && (
                      <Stage1
                        responses={msg.stage1}
                        timing={stageTimings.stage1}
                        modelStatuses={modelStatuses}
                        modelTimings={modelTimings}
                      />
                    )}

                    {msg.loading?.stage2 && (
                      <StageProgress
                        stage={2}
                        label="Stage 2: Peer rankings..."
                        timing={stageTimings.stage2}
                        onCancel={onCancelStream}
                      />
                    )}
                    {msg.stage2 && (
                      <Stage2
                        rankings={msg.stage2}
                        labelToModel={msg.metadata?.label_to_model}
                        aggregateRankings={msg.metadata?.aggregate_rankings}
                        timing={stageTimings.stage2}
                      />
                    )}

                    {msg.loading?.stage3 && (
                      <StageProgress
                        stage={3}
                        label="Stage 3: Final synthesis..."
                        timing={stageTimings.stage3}
                        onCancel={onCancelStream}
                      />
                    )}
                    {msg.stage3 && (
                      <Stage3
                        finalResponse={msg.stage3}
                        timing={stageTimings.stage3}
                      />
                    )}
                  </div>
                )}
              </div>
            ))}

            {/* Error UI with retry button */}
            {currentError && (
              <Card className="border-destructive bg-destructive/10">
                <CardContent className="pt-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
                    <div className="flex-1 space-y-3">
                      <div>
                        <p className="font-medium text-destructive">Deliberation Failed</p>
                        <p className="text-sm text-muted-foreground mt-1">
                          {currentError.message}
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={onRetry}
                          className="gap-2"
                        >
                          <RefreshCw className="h-4 w-4" />
                          Retry
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={onClearError}
                        >
                          Dismiss
                        </Button>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {conversation.messages.length === 0 && (
        <div className="border-t p-6 bg-background">
          <form onSubmit={handleSubmit} className="max-w-4xl mx-auto space-y-3">
            {/* Horizontal layout: Textarea on left, buttons stacked on right */}
            <div className="flex gap-3 items-stretch">
              <Textarea
                placeholder="Ask your question... (Shift+Enter for new line, Enter to send)"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading || isImproving}
                rows={3}
                className="resize-y flex-1"
              />
              <div className="flex flex-col gap-2 justify-center">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleImprovePrompt}
                  disabled={!input.trim() || isImproving || isLoading}
                  className="whitespace-nowrap"
                >
                  {isImproving ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Improving...
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4 mr-2" />
                      Improve Prompt
                    </>
                  )}
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={!input.trim() || isLoading || isImproving}
                  className="whitespace-nowrap"
                >
                  <Send className="h-4 w-4 mr-2" />
                  Send
                </Button>
              </div>
            </div>

            {originalPrompt && (
              <Card className="bg-muted/50">
                <CardContent className="pt-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm text-muted-foreground">Original prompt:</span>
                    <Button type="button" variant="ghost" size="sm" onClick={handleUndoImprovement}>
                      <Undo2 className="h-3 w-3 mr-1" />
                      Undo
                    </Button>
                  </div>
                  <p className="text-sm text-muted-foreground">{originalPrompt}</p>
                </CardContent>
              </Card>
            )}
          </form>
        </div>
      )}
    </div>
  );
}
