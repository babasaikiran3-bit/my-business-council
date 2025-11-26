import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  conversationId,
  onSendMessage,
  onCancelJob,
  onRetry,
  isLoading,
  showCost = true,
}) {
  const [input, setInput] = useState('');
  const messagesContainerRef = useRef(null);
  const textareaRef = useRef(null);
  
  // Check for pending jobs immediately (synchronous) - use conversationId from props
  const hasPendingJob = (() => {
    if (!conversationId) return false;
    try {
      const pendingJobs = JSON.parse(localStorage.getItem('pendingJobs') || '{}');
      return Object.values(pendingJobs).includes(conversationId);
    } catch {
      return false;
    }
  })();

  // Scroll to top whenever conversation changes
  useEffect(() => {
    if (messagesContainerRef.current) {
      messagesContainerRef.current.scrollTop = 0;
    }
  }, [conversation?.id]);

  // Auto-focus textarea on mobile when conversation changes (for new/empty conversations)
  useEffect(() => {
    if (conversation && conversation.messages.length === 0 && textareaRef.current) {
      // Small delay to ensure sidebar animation is complete
      const timer = setTimeout(() => {
        textareaRef.current?.focus();
      }, 350); // 350ms = sidebar animation (300ms) + buffer
      return () => clearTimeout(timer);
    }
  }, [conversation?.id]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    // Optional: Ctrl/Cmd+Enter to send (desktop users)
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSubmit(e);
    }
    // Enter without modifier = new line (default textarea behavior)
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <h2>Welcome to LLM Council</h2>
          <p>Create a new conversation to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
      <div className="messages-container" ref={messagesContainerRef}>
        {/* Show loading if pending job exists - but show user message first */}
        {hasPendingJob && (
          <>
            {/* Show user's question */}
            {conversation.messages.filter(m => m.role === 'user').map((msg, index) => (
              <div key={`user-${index}`} className="message-group">
                <div className="user-message">
                  <div className="message-label">You</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              </div>
            ))}
            
            {/* Show loading for assistant response */}
            <div className="message-group">
              <div className="assistant-message">
                <div className="message-label">LLM Council</div>
                <div className="stage-loading">
                  <div className="spinner"></div>
                  <div style={{ flex: 1 }}>
                    <span>Processing (Stage 1/2/3)...</span>
                    <div style={{ fontSize: '0.85em', color: '#666', marginTop: '4px' }}>
                      You can safely close this tab and come back later
                    </div>
                    {onCancelJob && conversation.messages.find(m => m.jobId) && (
                      <button 
                        className="cancel-button"
                        onClick={() => onCancelJob(conversation.messages.find(m => m.jobId)?.jobId)}
                        style={{ marginTop: '8px' }}
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </>
        )}
        
        {!hasPendingJob && conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a conversation</h2>
            <p>Ask a question to consult the LLM Council</p>
          </div>
        ) : !hasPendingJob ? (
          conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-label">You</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="message-label">LLM Council</div>

                  {/* Job Status (for async mode) */}
                  {msg.jobId && !msg.stage3 && !msg.stage1 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <div style={{ flex: 1 }}>
                        <span>
                          {(!msg.jobStatus || msg.jobStatus === 'pending') && 'Queued for processing...'}
                          {msg.jobStatus === 'processing' && 'Processing (Stage 1/2/3)...'}
                        </span>
                        <div style={{ fontSize: '0.85em', color: '#666', marginTop: '4px' }}>
                          You can safely close this tab and come back later
                        </div>
                        {onCancelJob && (
                          <button 
                            className="cancel-button"
                            onClick={() => onCancelJob(msg.jobId)}
                            style={{ marginTop: '8px' }}
                          >
                            Cancel
                          </button>
                        )}
                      </div>
                    </div>
                  )}

                  {/* Show retry button for failed jobs or incomplete responses */}
                  {((msg.jobStatus === 'failed') || 
                    (msg.role === 'assistant' && !msg.stage3 && !msg.jobId && !msg.loading)) && 
                    onRetry && (
                    <div className="error-message">
                      <span>Failed to process. </span>
                      <button className="retry-button" onClick={onRetry}>
                        Retry
                      </button>
                    </div>
                  )}

                  {/* Stage 1 */}
                  {msg.loading?.stage1 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 1: Collecting individual responses...</span>
                    </div>
                  )}
                  {msg.stage1 && (
                    <Stage1 
                      responses={msg.stage1}
                      stageCost={msg.metadata?.stage_costs?.stage1}
                      showCost={showCost}
                    />
                  )}

                  {/* Stage 2 */}
                  {msg.loading?.stage2 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 2: Peer rankings...</span>
                    </div>
                  )}
                  {msg.stage2 && (
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                      stageCost={msg.metadata?.stage_costs?.stage2}
                      showCost={showCost}
                    />
                  )}

                  {/* Stage 3 */}
                  {msg.loading?.stage3 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 3: Final synthesis...</span>
                    </div>
                  )}
                  {msg.stage3 && <Stage3 finalResponse={msg.stage3} showCost={showCost} />}
                </div>
              )}
            </div>
          ))
        ) : null}

        {isLoading && !hasPendingJob && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Consulting the council...</span>
          </div>
        )}

        {/* Show retry when last message is user (no assistant response) and no pending job */}
        {!hasPendingJob && !isLoading && conversation.messages.length > 0 && 
         conversation.messages[conversation.messages.length - 1].role === 'user' && 
         onRetry && (
          <div className="message-group">
            <div className="assistant-message">
              <div className="message-label">LLM Council</div>
              <div className="error-message">
                <span>Processing was cancelled or failed. </span>
                <button className="retry-button" onClick={onRetry}>
                  Retry
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {conversation.messages.length === 0 && (
        <form className="input-form" onSubmit={handleSubmit}>
          <textarea
            ref={textareaRef}
            className="message-input"
            placeholder="Type your question... (Ctrl+Enter or click Send)"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={3}
          />
          <button
            type="submit"
            className="send-button"
            disabled={!input.trim() || isLoading}
          >
            Send
          </button>
        </form>
      )}
    </div>
  );
}
