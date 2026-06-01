import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage0 from './Stage0';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import './ChatInterface.css';

const AGE_OPTIONS = [
  { label: 'Newborn (0-3mo)', value: 'newborn' },
  { label: 'Infant (3-12mo)', value: 'infant' },
  { label: 'Toddler (1-3yr)', value: 'toddler' },
  { label: 'Older child', value: 'older' },
];

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
}) {
  const [input, setInput] = useState('');
  const [ageValue, setAgeValue] = useState(AGE_OPTIONS[2].value);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      const ageLabel =
        AGE_OPTIONS.find((opt) => opt.value === ageValue)?.label ||
        AGE_OPTIONS[2].label;
      const content = `Child age: ${ageLabel}. Question: ${input}`;
      onSendMessage(content);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const safetyBanner = (
    <div className="safety-banner" role="note">
      ⚕️ General information from AI, based on cited medical sources — not a
      diagnosis or a substitute for professional care. If your child may be in
      danger, call your doctor or emergency services now.
    </div>
  );

  if (!conversation) {
    return (
      <div className="chat-interface">
        {safetyBanner}
        <div className="empty-state">
          <h2>Welcome to Parenting Roundtable</h2>
          <p>
            Science-backed parenting answers from a panel of AIs — with the
            sources, so you don't have to keep searching at 2am.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
      {safetyBanner}
      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a conversation</h2>
            <p>
              Science-backed parenting answers from a panel of AIs — with the
              sources, so you don't have to keep searching at 2am.
            </p>
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
                  <div className="message-label">Parenting Roundtable</div>

                  {/* Stage 0 */}
                  {msg.loading?.stage0 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Consulting trusted medical sources...</span>
                    </div>
                  )}
                  {msg.stage0 && (
                    <Stage0
                      evidenceBrief={msg.stage0?.evidence_brief}
                      sources={msg.stage0?.sources}
                    />
                  )}

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
            <span>Consulting the roundtable...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {conversation.messages.length === 0 && (
        <form className="input-form" onSubmit={handleSubmit}>
          <div className="input-main">
            <div className="age-selector">
              <label className="age-selector-label" htmlFor="child-age">
                Child's age
              </label>
              <select
                id="child-age"
                className="age-select"
                value={ageValue}
                onChange={(e) => setAgeValue(e.target.value)}
                disabled={isLoading}
              >
                {AGE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
            <textarea
              className="message-input"
              placeholder="Ask your question... (Shift+Enter for new line, Enter to send)"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
              rows={3}
            />
          </div>
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
