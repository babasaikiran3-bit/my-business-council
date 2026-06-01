import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage0 from './Stage0';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import EmergencyBanner from './EmergencyBanner';
import CalmProgress from './CalmProgress';
import { Logo, ShieldCheck, Send, ChevronDown, BadgeCheck } from './Icons';
import './ChatInterface.css';

// `days` is a representative age-in-days per band, sent as the typed `age_days`
// the backend safety triage uses (newborn <90, infant <365, toddler <1095).
// Phase 2 replaces this with an exact birthdate from the child profile.
const AGE_OPTIONS = [
  { label: '신생아', sub: '0–3개월', value: 'newborn', days: 45 },
  { label: '영아', sub: '3–12개월', value: 'infant', days: 225 },
  { label: '유아', sub: '1–3세', value: 'toddler', days: 730 },
  { label: '큰 아이', sub: '3세+', value: 'older', days: 1825 },
];

const TAGLINE =
  '믿을 수 있는 의료 출처를 바탕으로, AI 패널이 함께 검토한 육아 답변. 새벽 2시에 더 이상 혼자 검색하지 않아도 되도록.';

const EXAMPLES = [
  '38도 열이 나는데 해열제를 먹여도 될까요?',
  '6개월 아기 이유식, 어떻게 시작하면 좋을까요?',
  '밤에 자주 깨서 우는 아이, 어떻게 도와줄까요?',
  '아이가 자꾸 토하는데 언제 병원에 가야 하나요?',
];

const TRUST_SOURCES = ['질병관리청', '대한소아청소년과학회', '식약처', 'WHO', 'AAP'];

// True when there is multi-AI "machinery" worth tucking behind the expander.
// (Short-circuit emergency answers carry empty stages → no expander.)
function hasMachinery(m) {
  const stage0HasContent =
    m.stage0 && (m.stage0.evidence_brief || (m.stage0.sources && m.stage0.sources.length));
  return Boolean(stage0HasContent || (m.stage1 && m.stage1.length) || (m.stage2 && m.stage2.length));
}

export default function ChatInterface({ conversation, onSendMessage, isLoading }) {
  const [input, setInput] = useState('');
  const [ageValue, setAgeValue] = useState(AGE_OPTIONS[2].value);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Only follow the thread to the bottom once there are messages — on the welcome
  // screen this would otherwise scroll the hero out of view.
  useEffect(() => {
    if (conversation && conversation.messages.length > 0) {
      scrollToBottom();
    }
  }, [conversation]);

  const submit = () => {
    if (!input.trim() || isLoading) return;
    const option = AGE_OPTIONS.find((opt) => opt.value === ageValue) || AGE_OPTIONS[2];
    const content = `Child age: ${option.label} (${option.sub}). Question: ${input}`;
    // age_days travels as a typed field — the safety triage never parses it from the prompt.
    onSendMessage(content, option.days);
    setInput('');
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    submit();
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

  const safetyBanner = (
    <div className="safety-banner" role="note">
      <ShieldCheck size={16} />
      <span>
        신뢰할 수 있는 의료 출처 기반의 <strong>일반 정보</strong>입니다 — 진단·진료를
        대신하지 않아요. 위급해 보이면 지금 바로 <strong>119</strong> 또는 주치의에게 연락하세요.
      </span>
    </div>
  );

  return (
    <div className="chat-interface">
      {safetyBanner}

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

                  {/* Deterministic emergency interstitial (shows in <2s, before the answer) */}
                  {msg.emergency && <EmergencyBanner triage={msg.emergency} />}

                  {/* Lead with the answer; a calm wait shows until it's ready */}
                  {!msg.stage3 && !msg.error && <CalmProgress />}
                  {msg.error && (
                    <div className="answer-error" role="alert">
                      답변을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.
                    </div>
                  )}
                  {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}

                  {/* The multi-AI machinery, tucked behind an optional expander */}
                  {msg.stage3 && hasMachinery(msg) && (
                    <details className="how-we-got-this">
                      <summary className="how-we-got-this-summary">
                        <ChevronDown size={16} className="how-chevron" />
                        <span>어떻게 이 답을 찾았는지 보기</span>
                      </summary>
                      <div className="how-we-got-this-body">
                        {msg.stage0 && (
                          <Stage0
                            evidenceBrief={msg.stage0?.evidence_brief}
                            sources={msg.stage0?.sources}
                          />
                        )}
                        {msg.stage1 && <Stage1 responses={msg.stage1} />}
                        {msg.stage2 && (
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

            <div className="welcome-examples">
              {EXAMPLES.map((q) => (
                <button
                  key={q}
                  type="button"
                  className="example-chip"
                  onClick={() => pickExample(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {!hasThread && (
        <form className="composer" onSubmit={handleSubmit}>
          <div className="age-segment" role="group" aria-label="아이 나이 선택">
            <span className="age-segment-label">아이 나이</span>
            <div className="age-pills">
              {AGE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className={`age-pill ${ageValue === opt.value ? 'active' : ''}`}
                  aria-pressed={ageValue === opt.value}
                  onClick={() => setAgeValue(opt.value)}
                  disabled={isLoading}
                >
                  <span className="age-pill-label">{opt.label}</span>
                  <span className="age-pill-sub">{opt.sub}</span>
                </button>
              ))}
            </div>
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
      )}
    </div>
  );
}
