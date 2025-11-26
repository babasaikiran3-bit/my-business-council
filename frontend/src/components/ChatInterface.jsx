import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import './ChatInterface.css';

// 실시간 경과 시간 표시 컴포넌트
function RealtimeTimer({ startTime }) {
  const [elapsed, setElapsed] = useState(0);
  const [isAnimating, setIsAnimating] = useState(false);
  const [actualStartTime, setActualStartTime] = useState(() => {
    // 초기값: startTime이 있으면 사용, 없으면 현재 시간
    return startTime || Date.now() / 1000;
  });

  useEffect(() => {
    // startTime이 나중에 설정되면 업데이트 (더 정확한 서버 시간 사용)
    if (startTime) {
      setActualStartTime(startTime);
    }
  }, [startTime]);

  useEffect(() => {
    const updateElapsed = () => {
      const now = Date.now() / 1000; // 초 단위로 변환
      const newElapsed = now - actualStartTime;
      setElapsed(Math.max(0, newElapsed)); // 음수 방지
      // 애니메이션 효과를 위한 상태 변경
      setIsAnimating(true);
      setTimeout(() => setIsAnimating(false), 100);
    };

    updateElapsed(); // 즉시 업데이트
    const interval = setInterval(updateElapsed, 50); // 50ms마다 업데이트 (더 부드럽게)

    return () => clearInterval(interval);
  }, [actualStartTime]);

  function formatDuration(seconds) {
    if (!seconds || seconds < 0) return '0.0s';
    if (seconds < 1) {
      return `${(seconds * 1000).toFixed(0)}ms`;
    }
    if (seconds < 60) {
      return `${seconds.toFixed(1)}s`;
    }
    const mins = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(1);
    return `${mins}m ${secs}s`;
  }

  function formatTimestamp(timestamp) {
    if (!timestamp) return null;
    const date = new Date(timestamp * 1000);
    // 24-hour format: HH:mm:ss.S
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    const milliseconds = String(Math.floor(date.getMilliseconds() / 100)).padStart(1, '0');
    return `${hours}:${minutes}:${seconds}.${milliseconds}`;
  }

  return (
    <div className="realtime-timing">
      {actualStartTime && (
        <span className="timing-start">Started: {formatTimestamp(actualStartTime)}</span>
      )}
      <span className={`timing-elapsed ${isAnimating ? 'pulse' : ''}`}>
        Elapsed: {formatDuration(elapsed)}
      </span>
    </div>
  );
}

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
}) {
  const [input, setInput] = useState('');
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
      onSendMessage(input);
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
                      <div className="loading-content">
                        <div className="spinner"></div>
                        <span>Running Stage 1: Collecting individual responses...</span>
                      </div>
                      <RealtimeTimer startTime={msg.timings?.stage1?.start} />
                    </div>
                  )}
                  {msg.stage1 && <Stage1 responses={msg.stage1} timings={msg.timings?.stage1} />}

                  {/* Stage 2 */}
                  {msg.loading?.stage2 && (
                    <div className="stage-loading">
                      <div className="loading-content">
                        <div className="spinner"></div>
                        <span>Running Stage 2: Peer rankings...</span>
                      </div>
                      <RealtimeTimer startTime={msg.timings?.stage2?.start} />
                    </div>
                  )}
                  {msg.stage2 && (
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                      timings={msg.timings?.stage2}
                    />
                  )}

                  {/* Stage 3 */}
                  {msg.loading?.stage3 && (
                    <div className="stage-loading">
                      <div className="loading-content">
                        <div className="spinner"></div>
                        <span>Running Stage 3: Final synthesis...</span>
                      </div>
                      <RealtimeTimer startTime={msg.timings?.stage3?.start} />
                    </div>
                  )}
                  {msg.stage3 && <Stage3 finalResponse={msg.stage3} timings={msg.timings?.stage3} />}
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
          <textarea
            className="message-input"
            placeholder="Ask your question... (Shift+Enter for new line, Enter to send)"
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
