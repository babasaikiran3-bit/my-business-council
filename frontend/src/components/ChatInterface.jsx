import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../api';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import { Stage1Progress, StageProgress } from './ProgressIndicator';
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Sparkles, Send, Undo2, Loader2, User, Users } from "lucide-react"
import { cn } from "@/lib/utils"

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  stageTimings,
  modelStatuses,
  modelTimings,
}) {
  const [input, setInput] = useState('');
  const [isImproving, setIsImproving] = useState(false);
  const [originalPrompt, setOriginalPrompt] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading && !isImproving) {
      onSendMessage(input);
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
    } catch (error) {
      console.error('Failed to improve prompt:', error);
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
      <div className="flex-1 flex items-center justify-center bg-background">
        <div className="text-center">
          <h2 className="text-2xl font-semibold text-foreground mb-2">Welcome to LLM Council</h2>
          <p className="text-muted-foreground">Create a new conversation to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-background h-screen">
      <ScrollArea className="flex-1 p-6">
        {conversation.messages.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <h2 className="text-2xl font-semibold text-foreground mb-2">Start a conversation</h2>
              <p className="text-muted-foreground">Ask a question to consult the LLM Council</p>
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
                    <div className="flex items-center gap-2 text-sm font-medium text-foreground">
                      <Users className="h-4 w-4" />
                      LLM Council
                    </div>

                    {msg.loading?.stage1 && Object.keys(modelStatuses).length > 0 && (
                      <Stage1Progress
                        modelStatuses={modelStatuses}
                        timing={stageTimings.stage1}
                      />
                    )}
                    {msg.loading?.stage1 && Object.keys(modelStatuses).length === 0 && (
                      <StageProgress
                        stage={1}
                        label="Stage 1: Collecting responses..."
                        timing={stageTimings.stage1}
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
          </div>
        )}

        <div ref={messagesEndRef} />
      </ScrollArea>

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
