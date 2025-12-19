import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { toast } from 'sonner';
import { api } from '../api';
import { isConnectionError } from '@/contexts/ConnectionErrorContext';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import { Stage1Progress, StageProgress, RecoveryProgress } from './ProgressIndicator';
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import { Sparkles, Send, Undo2, Loader2, User, Users, AlertCircle, RefreshCw, StopCircle, PlayCircle } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Determine the resume stage label based on available stage data.
 * Returns null if no resume is possible (no partial data).
 */
function getResumeStageInfo(msg) {
  if (msg.response_status !== 'failed') return null;

  const hasStage1 = msg.stage1 && msg.stage1.length > 0;
  const hasStage2 = msg.stage2 && msg.stage2.length > 0;
  const hasStage3 = msg.stage3 && Object.keys(msg.stage3).length > 0;

  // If all stages complete, nothing to resume
  if (hasStage3) return null;

  if (hasStage2) {
    return { stage: 3, label: 'Resume from Stage 3' };
  } else if (hasStage1) {
    return { stage: 2, label: 'Resume from Stage 2' };
  } else {
    return { stage: 1, label: 'Restart Deliberation' };
  }
}

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  isCreatingConversation = false,
  stageTimings,
  modelStatuses,
  modelTimings,
  currentError,
  onRetry,
  onClearError,
  onCancelStream,
  // Polling state for recovery after browser refresh
  pollingStatus = null,
  pollingResponseId = null,
  onStopPolling = null,
  onCancelDeliberation = null,
  isCancellingDeliberation = false,
  // Resume functionality for failed persisted responses
  onResumeDeliberation = null,
  resumingResponseId = null,
}) {
  const [input, setInput] = useState('');
  const [isImproving, setIsImproving] = useState(false);
  const [originalPrompt, setOriginalPrompt] = useState(null);
  const messagesEndRef = useRef(null);
  const scrollAreaRef = useRef(null);
  const prevMessageCountRef = useRef(0);
  const userScrolledUpRef = useRef(false);

  // Refs for stage containers to enable auto-scroll to stage headers
  const stage1Ref = useRef(null);
  const stage2Ref = useRef(null);
  const stage3Ref = useRef(null);

  // Track previous stage states to detect transitions
  const prevStageStatesRef = useRef({
    stage1Started: false,
    stage2Started: false,
    stage3Started: false,
  });

  // Track if current deliberation was initiated by user in this session
  // When true, skip stage auto-scroll to avoid disrupting user who just sent message
  const userInitiatedMessageRef = useRef(false);

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

  // Track if this is the first render for this conversation ID
  const lastSeenConversationIdRef = useRef(null);

  // Helper to determine which stage ref to scroll to based on stage timings
  // Used for in-progress conversations when switching to them
  const getActiveStageRef = () => {
    if (stageTimings?.stage3?.startTime != null) return { ref: stage3Ref, name: 'Stage 3' };
    if (stageTimings?.stage2?.startTime != null) return { ref: stage2Ref, name: 'Stage 2' };
    if (stageTimings?.stage1?.startTime != null) return { ref: stage1Ref, name: 'Stage 1' };
    return null;
  };

  // Helper to check if conversation has completed all stages (has Stage 3 data)
  // The message structure from backend is: { role: "assistant", stage1: [...], stage2: [...], stage3: {...} }
  const isCompletedConversation = () => {
    const messages = conversation?.messages || [];
    if (messages.length === 0) return false;

    // Find the last assistant message (has role: "assistant")
    // Messages alternate: user, assistant, user, assistant...
    const lastAssistantMessage = [...messages].reverse().find(msg => msg.role === 'assistant');
    if (!lastAssistantMessage) return false;

    // Check if it has stage3 data (completed conversation)
    // stage3 is an object like { model: "...", response: "..." }
    const hasStage3 = lastAssistantMessage.stage3 &&
                      typeof lastAssistantMessage.stage3 === 'object' &&
                      Object.keys(lastAssistantMessage.stage3).length > 0;

    console.log('[ChatInterface] isCompletedConversation check:', {
      lastAssistantMessage: lastAssistantMessage ? 'found' : 'not found',
      hasStage3,
      stage3Keys: lastAssistantMessage?.stage3 ? Object.keys(lastAssistantMessage.stage3) : []
    });

    return hasStage3;
  };

  // Combined effect for conversation switching and message count changes
  // This ensures proper ordering: conversation switch detection happens before message count logic
  useEffect(() => {
    const currentMessageCount = conversation?.messages?.length || 0;
    const prevMessageCount = prevMessageCountRef.current;
    const isConversationSwitch = conversation?.id !== lastSeenConversationIdRef.current;

    if (isConversationSwitch) {
      // Handle conversation switch
      console.log('[ChatInterface] Conversation ID changed:', {
        from: lastSeenConversationIdRef.current,
        to: conversation?.id,
        newMessageCount: currentMessageCount,
        isLoading
      });

      // Reset all scroll-related state for the new conversation
      userScrolledUpRef.current = false;
      prevMessageCountRef.current = currentMessageCount;
      lastSeenConversationIdRef.current = conversation?.id;

      // Reset user-initiated flag since we're switching to a different conversation
      userInitiatedMessageRef.current = false;

      // Reset previous stage states when switching conversations
      prevStageStatesRef.current = {
        stage1Started: false,
        stage2Started: false,
        stage3Started: false,
      };

      // Scroll to appropriate position based on conversation state
      // Use a longer delay (300ms) to ensure DOM has fully rendered the conversation content
      // This is necessary because React needs time to:
      // 1. Update the virtual DOM
      // 2. Render all Stage components
      // 3. Attach refs to the DOM elements
      setTimeout(() => {
        console.log('[ChatInterface] Scroll timeout fired, checking conditions:', {
          isLoading,
          stage3RefCurrent: stage3Ref.current ? 'exists' : 'null',
          scrollAreaRefCurrent: scrollAreaRef.current ? 'exists' : 'null'
        });

        // Check if this is a completed conversation (has Stage 3 data)
        const isCompleted = isCompletedConversation();

        if (isCompleted) {
          // Completed conversation: scroll to Stage 3 (final synthesis)
          console.log('[ChatInterface] Switching to completed conversation, scrolling to Stage 3');
          if (stage3Ref.current) {
            scrollToStageHeader(stage3Ref);
          } else {
            console.warn('[ChatInterface] Stage 3 ref not available yet');
          }
        } else if (isLoading) {
          // In-progress conversation: scroll to currently active stage
          const activeStage = getActiveStageRef();
          if (activeStage) {
            console.log(`[ChatInterface] Switching to in-progress conversation, scrolling to ${activeStage.name}`);
            scrollToStageHeader(activeStage.ref);
          } else {
            console.log('[ChatInterface] In-progress but no active stage yet');
          }
        } else {
          console.log('[ChatInterface] Empty or new conversation, staying at top');
        }
      }, 300);
    } else {
      // Same conversation - check if message count increased
      console.log('[ChatInterface] Message count effect (same conversation):', {
        conversationId: conversation?.id,
        currentMessageCount,
        prevMessageCount,
        userScrolledUp: userScrolledUpRef.current,
        isLoading,
        willScroll: currentMessageCount > prevMessageCount && !userScrolledUpRef.current
      });

      // Only scroll to bottom if:
      // - Message count increased (new message added)
      // - User hasn't manually scrolled up
      if (currentMessageCount > prevMessageCount && !userScrolledUpRef.current) {
        scrollToBottom();
      }

      // Update previous count
      prevMessageCountRef.current = currentMessageCount;
    }
  }, [conversation?.id, conversation?.messages?.length, isLoading, stageTimings]);

  // Helper to scroll a stage header to the top of the viewport
  const scrollToStageHeader = (stageRef) => {
    if (!stageRef?.current || !scrollAreaRef.current) return;

    const container = scrollAreaRef.current;
    const stageElement = stageRef.current;

    // Calculate the offset of the stage element relative to the scroll container
    const containerRect = container.getBoundingClientRect();
    const stageRect = stageElement.getBoundingClientRect();
    const offsetTop = stageRect.top - containerRect.top + container.scrollTop;

    // Scroll so the stage header is at the top of the viewport with a small padding
    container.scrollTo({
      top: offsetTop - 16, // 16px padding from top
      behavior: 'smooth',
    });
  };

  // Auto-scroll to stage headers when stages begin
  // Only triggers when:
  // 1. isLoading is true (active deliberation)
  // 2. User did NOT initiate the message (switched to an in-progress conversation)
  // When user sends a message themselves, they're already viewing - no need to auto-scroll
  useEffect(() => {
    const stage1Started = stageTimings?.stage1?.startTime != null;
    const stage2Started = stageTimings?.stage2?.startTime != null;
    const stage3Started = stageTimings?.stage3?.startTime != null;

    const prev = prevStageStatesRef.current;

    // Only auto-scroll if:
    // - Active deliberation (isLoading = true)
    // - User did NOT initiate this message (they switched to an in-progress conversation)
    if (isLoading && !userInitiatedMessageRef.current) {
      // Detect stage transitions (stage just started)
      if (stage3Started && !prev.stage3Started) {
        // Stage 3 just began - scroll to Stage 3 header
        console.log('[ChatInterface] Stage 3 started, scrolling to Stage 3 header');
        // Use a small delay to ensure the DOM has updated
        setTimeout(() => scrollToStageHeader(stage3Ref), 50);
      } else if (stage2Started && !prev.stage2Started) {
        // Stage 2 just began - scroll to Stage 2 header
        console.log('[ChatInterface] Stage 2 started, scrolling to Stage 2 header');
        setTimeout(() => scrollToStageHeader(stage2Ref), 50);
      } else if (stage1Started && !prev.stage1Started) {
        // Stage 1 just began - scroll to Stage 1 header
        console.log('[ChatInterface] Stage 1 started, scrolling to Stage 1 header');
        setTimeout(() => scrollToStageHeader(stage1Ref), 50);
      }
    }

    // Reset user-initiated flag when loading completes
    if (!isLoading && userInitiatedMessageRef.current) {
      userInitiatedMessageRef.current = false;
    }

    // Update previous states
    prevStageStatesRef.current = {
      stage1Started,
      stage2Started,
      stage3Started,
    };
  }, [stageTimings?.stage1?.startTime, stageTimings?.stage2?.startTime, stageTimings?.stage3?.startTime, isLoading]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading && !isImproving) {
      // Mark this as a user-initiated message to skip stage auto-scroll
      userInitiatedMessageRef.current = true;
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
      // Skip toast for connection errors - the ConnectionErrorBanner handles those
      if (!isConnectionError(error)) {
        toast.error('Failed to improve prompt. Please try again.');
      }
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

  // Note: conversation is always provided (draft or persisted), so no early return needed
  // The empty state is handled below when conversation.messages is empty

  return (
    <div className="flex flex-col bg-background flex-1 min-h-0 overflow-hidden">
      {/* Using native scrolling for reliability - flex-1 min-h-0 pattern with overflow-y-auto */}
      <div ref={scrollAreaRef} className="flex-1 min-h-0 overflow-y-auto" onScroll={handleScroll}>
        <div className="p-6">
          {conversation.messages.length === 0 ? (
            <div className="flex flex-col items-center pt-8 pb-6 px-6">
              {/* Header text */}
              <div className="text-center mb-6">
                <h2 className="text-2xl font-semibold text-foreground mb-2">Start a conversation</h2>
                <p className="text-muted-foreground">Ask a question to consult Eternal Copilot</p>
              </div>

              {/* Input form - prominently placed at top */}
              <form onSubmit={handleSubmit} className="w-full max-w-4xl space-y-3">
                {/* Horizontal layout: Textarea on left, buttons stacked on right */}
                <div className="flex gap-3 items-stretch">
                  <Textarea
                    placeholder="Ask your question... (Shift+Enter for new line, Enter to send)"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={isLoading || isImproving || isCreatingConversation}
                    rows={3}
                    className="resize-y flex-1"
                    autoFocus
                  />
                  <div className="flex flex-col gap-2 justify-center">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleImprovePrompt}
                      disabled={!input.trim() || isImproving || isLoading || isCreatingConversation}
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
                      disabled={!input.trim() || isLoading || isImproving || isCreatingConversation}
                      className="whitespace-nowrap"
                    >
                      {isCreatingConversation ? (
                        <>
                          <Loader2 className="h-4 w-4 animate-spin mr-2" />
                          Creating...
                        </>
                      ) : (
                        <>
                          <Send className="h-4 w-4 mr-2" />
                          Send
                        </>
                      )}
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

                    {/* Stage 1 container with ref for auto-scroll */}
                    <div ref={stage1Ref}>
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
                    </div>

                    {/* Stage 2 container with ref for auto-scroll */}
                    <div ref={stage2Ref}>
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
                    </div>

                    {/* Stage 3 container with ref for auto-scroll */}
                    <div ref={stage3Ref}>
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

                    {/* Recovery indicator when polling for in-progress deliberation after browser refresh */}
                    {pollingStatus && !msg.loading && index === conversation.messages.length - 1 && (
                      <RecoveryProgress
                        status={pollingStatus}
                        onStopPolling={onStopPolling}
                        onCancel={pollingResponseId && onCancelDeliberation ? () => onCancelDeliberation(pollingResponseId) : null}
                        isCancelling={isCancellingDeliberation}
                      />
                    )}

                    {/* Resume button for failed deliberations with partial stage data */}
                    {(() => {
                      const resumeInfo = getResumeStageInfo(msg);
                      const isResuming = resumingResponseId === msg.response_id;
                      const isLastMessage = index === conversation.messages.length - 1;

                      // Only show for last assistant message with failed status and resumable state
                      if (!resumeInfo || !isLastMessage || !msg.response_id || !onResumeDeliberation) return null;
                      // Don't show if currently polling (still checking status)
                      if (pollingStatus) return null;
                      // Hide the card once resume has started (isResuming true means SSE stream is active)
                      // The progress indicators will show stage progress instead
                      if (isResuming) return null;

                      return (
                        <Card className="border-amber-500/50 bg-amber-50/30">
                          <CardContent className="pt-4">
                            <div className="flex items-start gap-3">
                              <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                              <div className="flex-1 space-y-3">
                                <div>
                                  <p className="font-medium text-amber-700">Deliberation Incomplete</p>
                                  <p className="text-sm text-muted-foreground mt-1">
                                    This deliberation didn't complete.{' '}
                                    {resumeInfo.stage > 1 && `Stage ${resumeInfo.stage - 1} data is available and can be reused.`}
                                  </p>
                                </div>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => onResumeDeliberation(msg.response_id)}
                                  disabled={isResuming}
                                  className="gap-2 border-amber-500/50 hover:bg-amber-100/50"
                                >
                                  {isResuming ? (
                                    <>
                                      <Loader2 className="h-4 w-4 animate-spin" />
                                      Resuming...
                                    </>
                                  ) : (
                                    <>
                                      <PlayCircle className="h-4 w-4" />
                                      {resumeInfo.label}
                                    </>
                                  )}
                                </Button>
                              </div>
                            </div>
                          </CardContent>
                        </Card>
                      );
                    })()}
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
    </div>
  );
}
