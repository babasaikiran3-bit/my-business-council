import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { api } from '../api';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
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
    // Submit on Enter (without Shift)
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
      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a conversation</h2>
            <p>Ask a question to consult the LLM Council</p>
          </div>
        ) : (
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

                  {/* Stage 1 */}
                  {msg.loading?.stage1 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 1: Collecting individual responses...</span>
                    </div>
                  )}
                  {msg.stage1 && <Stage1 responses={msg.stage1} />}

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
                    />
                  )}

                  {/* Stage 3 */}
                  {msg.loading?.stage3 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 3: Final synthesis...</span>
                    </div>
                  )}
                  {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Consulting the council...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {conversation.messages.length === 0 && (
        <form className="input-form" onSubmit={handleSubmit}>
          <div className="input-section">
            <textarea
              className="message-input"
              placeholder="Ask your question... (Shift+Enter for new line, Enter to send)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading || isImproving}
              rows={3}
            />

            {/* Show original prompt for comparison when improved */}
            {originalPrompt && (
              <div className="original-prompt-notice">
                <div className="original-prompt-header">
                  <span>📝 Original prompt:</span>
                  <button
                    type="button"
                    className="undo-button"
                    onClick={handleUndoImprovement}
                  >
                    ↩ Undo
                  </button>
                </div>
                <div className="original-prompt-text">{originalPrompt}</div>
              </div>
            )}
          </div>

          <div className="button-group">
            <button
              type="button"
              className="improve-button"
              onClick={handleImprovePrompt}
              disabled={!input.trim() || isImproving || isLoading}
            >
              {isImproving ? (
                <>
                  <span className="spinner spinner-small"></span>
                  <span>Improving...</span>
                </>
              ) : (
                '✨ Improve Prompt'
              )}
            </button>
            <button
              type="submit"
              className="send-button"
              disabled={!input.trim() || isLoading || isImproving}
            >
              Send
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
