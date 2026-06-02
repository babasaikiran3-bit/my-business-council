import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage0 from './Stage0';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import EmergencyBanner from './EmergencyBanner';
import CalmProgress from './CalmProgress';
import ChildChip from './ChildChip';
import { Logo, Send, ChevronDown, BadgeCheck, Plus } from './Icons';
import { ageLabel } from '../lib/age';
import './ChatInterface.css';

const TAGLINE =
  '믿을 수 있는 의료 출처를 바탕으로, AI 패널이 함께 검토한 육아 답변. 새벽 2시에 더 이상 혼자 검색하지 않아도 되도록.';

const TRUST_SOURCES = ['질병관리청', '대한소아청소년과학회', '식약처', 'WHO', 'AAP'];

// Welcome-state category entry (decision 2). Hidden once a thread exists.
const CATEGORIES = [
  { id: 'fever', label: '열·체온', examples: ['38도 열이 나는데 해열제를 먹여도 될까요?', '열이 며칠째 안 떨어져요. 언제 병원에 가야 하나요?'] },
  { id: 'sleep', label: '수면', examples: ['밤에 자주 깨서 우는 아이, 어떻게 도와줄까요?', '수면 교육은 언제 시작하면 좋을까요?'] },
  { id: 'feeding', label: '먹이기', examples: ['6개월 아기 이유식, 어떻게 시작하면 좋을까요?', '분유를 잘 안 먹는데 괜찮을까요?'] },
  { id: 'development', label: '발달', examples: ['또래보다 늦게 걷는 것 같아요. 정상인가요?', '말이 느린데 언제 검사를 받아야 하나요?'] },
  { id: 'other', label: '기타', examples: ['아이가 자꾸 토하는데 언제 병원에 가야 하나요?', '예방접종 후 열이 나면 어떻게 해야 하나요?'] },
];

// True when there is multi-AI "machinery" worth tucking behind the expander.
function hasMachinery(m) {
  const stage0HasContent =
    m.stage0 && (m.stage0.evidence_brief || (m.stage0.sources && m.stage0.sources.length));
  return Boolean(stage0HasContent || (m.stage1 && m.stage1.length) || (m.stage2 && m.stage2.length));
}

export default function ChatInterface({
  conversation,
  onSendMessage,
  onRetry,
  onNewQuestion,
  isLoading,
  activeChild,
  onEditChild,
  composerLocked = false,
  lockedNode = null,
}) {
  const [input, setInput] = useState('');
  const [category, setCategory] = useState('other');
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    if (conversation && conversation.messages.length > 0) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [conversation]);

  const submit = () => {
    if (!input.trim() || isLoading) return;
    if (input.length > 5000) return; // align to the server cap (MAX_MESSAGE_CHARS)
    const cat = CATEGORIES.find((c) => c.id === category);
    const catPart = category && category !== 'other' ? `[${cat.label}] ` : '';
    const agePart = activeChild ? `아이 나이: ${ageLabel(activeChild.birthdate)}. ` : '';
    onSendMessage(`${catPart}${agePart}질문: ${input}`);
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const pickExample = (q) => {
    setInput(q);
    textareaRef.current?.focus();
  };

  const hasThread = conversation && conversation.messages.length > 0;
  const lastMsg = hasThread ? conversation.messages[conversation.messages.length - 1] : null;
  const threadDone = lastMsg && lastMsg.role === 'assistant' && (lastMsg.stage3 || lastMsg.error);
  const activeCategory = CATEGORIES.find((c) => c.id === category) || CATEGORIES[4];

  return (
    <div className="chat-interface">
      <div className="messages-container">
        {hasThread ? (
          conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-label">내 질문</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="assistant-id">
                    <span className="assistant-avatar" aria-hidden="true">
                      <Logo size={26} />
                    </span>
                    <span className="message-label">부모 라운드테이블</span>
                  </div>

                  {msg.emergency && <EmergencyBanner triage={msg.emergency} />}

                  {/* Show verified sources as soon as Stage 0 lands — something real at ~3-5s */}
                  {!msg.stage3 && msg.stage0?.sources?.length > 0 && (
                    <div className="early-sources">
                      <span className="early-sources-label">
                        <BadgeCheck size={14} /> 출처 확인됨
                      </span>
                      {msg.stage0.sources.slice(0, 5).map((s, i) => (
                        <a
                          key={i}
                          className="early-source-chip"
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {s.title || s.url}
                        </a>
                      ))}
                    </div>
                  )}

                  {!msg.stage3 && !msg.error && <CalmProgress />}
                  {msg.error && (
                    <div className="answer-error" role="alert">
                      <span>답변을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.</span>
                      {onRetry && (
                        <button type="button" className="retry-button" onClick={onRetry} disabled={isLoading}>
                          다시 시도
                        </button>
                      )}
                    </div>
                  )}
                  {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}

                  {msg.stage3 && hasMachinery(msg) && (
                    <details className="how-we-got-this">
                      <summary className="how-we-got-this-summary">
                        <ChevronDown size={16} className="how-chevron" />
                        <span>근거 보기</span>
                      </summary>
                      <div className="how-we-got-this-body">
                        {msg.stage0 && (msg.stage0.evidence_brief || msg.stage0.sources?.length > 0) && (
                          <Stage0 evidenceBrief={msg.stage0?.evidence_brief} sources={msg.stage0?.sources} />
                        )}
                        {msg.stage1?.length > 0 && <Stage1 responses={msg.stage1} />}
                        {msg.stage2?.length > 0 && (
                          <Stage2
                            rankings={msg.stage2}
                            labelToModel={msg.metadata?.label_to_model}
                            aggregateRankings={msg.metadata?.aggregate_rankings}
                          />
                        )}
                      </div>
                    </details>
                  )}
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="welcome">
            <div className="welcome-mark">
              <Logo size={64} />
            </div>
            <h1 className="welcome-title">무엇이든 물어보세요</h1>
            <p className="welcome-tagline">{TAGLINE}</p>
            <div className="welcome-trust">
              <BadgeCheck size={15} />
              <span>{TRUST_SOURCES.join(' · ')} 등 신뢰할 수 있는 출처를 확인해요</span>
            </div>
          </div>
        )}

        {/* Quiet disclaimer footer + next-step, shown once an answer exists (Wave 5) */}
        {threadDone && (
          <div className="thread-footer">
            <p className="thread-disclaimer">
              이 답변은 일반적인 정보이며 의학적 진단을 대신하지 않습니다. 위급하면 119 또는 주치의에게 연락하세요.
            </p>
            <button type="button" className="new-question-cta" onClick={onNewQuestion}>
              <Plus size={17} />
              <span>다른 질문 하기</span>
            </button>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {!hasThread && (
        composerLocked ? (
          <div className="composer-locked">{lockedNode}</div>
        ) : (
          <form className="composer" onSubmit={(e) => { e.preventDefault(); submit(); }}>
            <div className="composer-context">
              <ChildChip child={activeChild} onClick={onEditChild} />
            </div>

            <div className="category-pills" role="group" aria-label="질문 종류">
              {CATEGORIES.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className={`category-pill ${category === c.id ? 'active' : ''}`}
                  aria-pressed={category === c.id}
                  onClick={() => setCategory(c.id)}
                >
                  {c.label}
                </button>
              ))}
            </div>

            <div className="category-examples">
              {activeCategory.examples.map((q) => (
                <button key={q} type="button" className="example-chip" onClick={() => pickExample(q)}>
                  {q}
                </button>
              ))}
            </div>

            <div className="composer-input-row">
              <textarea
                ref={textareaRef}
                className="message-input"
                placeholder="궁금한 점을 편하게 적어주세요…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                maxLength={5000}
                rows={2}
              />
              <button
                type="submit"
                className="send-button"
                disabled={!input.trim() || isLoading}
                aria-label="질문 보내기"
              >
                <Send size={20} />
              </button>
            </div>
            <div className="composer-hint">Enter 전송 · Shift+Enter 줄바꿈</div>
          </form>
        )
      )}
    </div>
  );
}
