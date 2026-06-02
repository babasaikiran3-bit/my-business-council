import { Link } from 'react-router-dom';
import ExampleCard from '../components/ExampleCard';
import { Logo, Send, BadgeCheck, MessageHeart, ArrowRight, ShieldCheck } from '../components/Icons';
import './Landing.css';

const STEPS = [
  { Icon: Send, title: '질문을 입력하면', body: '열, 수면, 이유식 — 무엇이든 편하게 물어보세요.' },
  { Icon: BadgeCheck, title: '검증된 자료를 찾아요', body: '질병관리청·AAP·WHO 등 신뢰할 수 있는 의료 출처를 검색해요.' },
  { Icon: MessageHeart, title: '하나의 명확한 답을 드려요', body: '여러 AI가 교차검증한 뒤, 헷갈리지 않는 답 하나로 정리해요.' },
];

const TRUST = ['질병관리청', '대한소아청소년과학회', '식약처', 'AAP', 'WHO', 'CDC', 'NHS', 'Mayo Clinic'];

export default function Landing() {
  return (
    <div className="landing">
      <header className="landing-nav">
        <div className="landing-brand">
          <Logo size={32} />
          <span>부모 라운드테이블</span>
        </div>
        <Link to="/start" className="landing-nav-cta">시작하기</Link>
      </header>

      {/* Hero */}
      <section className="landing-hero">
        <h1 className="landing-headline">
          새벽 2시, 아이가 아플 때.<br />
          <span className="landing-headline-accent">믿을 수 있는 답을 드려요.</span>
        </h1>
        <p className="landing-subhead">
          대한소아청소년과학회, CDC, WHO 등 검증된 의료 출처를 바탕으로 —
          인터넷의 수많은 정보에 더 이상 혼자 휩쓸리지 않도록.
        </p>
        <Link to="/start" className="landing-cta">
          <span>무료로 시작하기</span>
          <ArrowRight size={20} />
        </Link>
        <p className="landing-cta-note">로그인 없이도 첫 질문은 바로 해보실 수 있어요.</p>
      </section>

      {/* How it works */}
      <section className="landing-section">
        <h2 className="landing-h2">이렇게 작동해요</h2>
        <div className="landing-steps">
          {STEPS.map((s, i) => (
            <div key={s.title} className="landing-step">
              <div className="landing-step-icon"><s.Icon size={24} /></div>
              <span className="landing-step-num">{i + 1}</span>
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Trust */}
      <section className="landing-section landing-trust-section">
        <p className="landing-trust-caption">
          AI가 지어낸 정보가 아니라, 이미 검증된 의료 출처에서 인용합니다.
        </p>
        <div className="landing-trust-strip">
          {TRUST.map((t) => <span key={t} className="landing-trust-item">{t}</span>)}
        </div>
      </section>

      {/* Live example */}
      <section className="landing-section">
        <h2 className="landing-h2">실제 답변 예시</h2>
        <p className="landing-section-sub">이렇게 답해드려요 — 출처와 응급 안내까지 한눈에.</p>
        <ExampleCard />
      </section>

      {/* Honest limitations */}
      <section className="landing-section">
        <div className="landing-limits">
          <ShieldCheck size={22} />
          <p>
            이 서비스는 의학적 진단을 대신하지 않습니다. 위급한 상황에서는 119 또는 주치의에게
            바로 연락하세요.
          </p>
        </div>
      </section>

      {/* Final CTA */}
      <section className="landing-final">
        <h2>지금 바로 물어보세요</h2>
        <Link to="/start" className="landing-cta">
          <span>무료로 시작하기</span>
          <ArrowRight size={20} />
        </Link>
      </section>

      <footer className="landing-footer">
        <div className="landing-footer-brand">
          <Logo size={24} />
          <span>부모 라운드테이블</span>
        </div>
        <p>신뢰할 수 있는 의료 출처 기반의 육아 정보 · 파일럿 v0.1.0</p>
      </footer>
    </div>
  );
}
