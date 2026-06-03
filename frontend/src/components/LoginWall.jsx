import { api } from '../api';
import { useApp } from '../context/appContext';
import { ShieldCheck, BadgeCheck, Users, KakaoGlyph, NaverGlyph } from './Icons';
import './LoginWall.css';

const PROVIDER_LABELS = {
  kakao: { label: '카카오로 계속하기', Glyph: KakaoGlyph },
  naver: { label: '네이버로 계속하기', Glyph: NaverGlyph },
};

const REASONS = [
  { Icon: BadgeCheck, text: 'AI가 지어낸 말이 아니라, 질병관리청·AAP·WHO 등 검증된 의료 출처에서 인용해요.' },
  { Icon: Users, text: '여러 AI가 같은 근거로 답을 내고 서로 교차검증한 뒤, 하나의 명확한 답을 드려요.' },
  { Icon: ShieldCheck, text: '응급 신호는 답변을 기다리지 않고 즉시 알려드려요. 안전이 늘 먼저예요.' },
];

/**
 * Shown after a first-time (anonymous) parent's one free question. Reinforces why the
 * answer they just saw is trustworthy, then asks them to log in to keep going.
 */
export default function LoginWall() {
  const { enabledProviders, clearFreeAsk } = useApp();

  return (
    <div className="login-wall">
      <div className="login-wall-badge">
        <ShieldCheck size={26} />
      </div>
      <h2 className="login-wall-title">첫 답변, 어떠셨나요?</h2>
      <p className="login-wall-sub">
        계속 질문하시려면 로그인해 주세요. 아이 프로필과 질문 기록이 안전하게 저장돼요.
      </p>

      <ul className="login-wall-reasons">
        {REASONS.map((r) => (
          <li key={r.text}>
            <span className="login-wall-reason-icon"><r.Icon size={18} /></span>
            <span>{r.text}</span>
          </li>
        ))}
      </ul>

      {enabledProviders.length > 0 ? (
        <div className="login-wall-actions">
          {enabledProviders.map((p) => {
            const { label, Glyph } = PROVIDER_LABELS[p];
            return (
              <a key={p} className={`login-wall-btn login-wall-btn-${p}`} href={api.loginUrl(p)}>
                <Glyph size={18} />
                <span>{label}</span>
              </a>
            );
          })}
        </div>
      ) : (
        <div className="login-wall-demo">
          <p>지금은 데모 환경이라 소셜 로그인이 설정되어 있지 않아요.</p>
          <button type="button" className="login-wall-demo-btn" onClick={clearFreeAsk}>
            데모로 계속하기
          </button>
        </div>
      )}
    </div>
  );
}
