import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api';
import { useApp } from '../context/appContext';
import { toBirthdate } from '../lib/age';
import { Logo, ShieldCheck, BadgeCheck, ArrowRight, KakaoGlyph, NaverGlyph, Check } from '../components/Icons';
import './Start.css';

const REQUIRED_CONSENTS = ['sensitive_health', 'child_data_by_guardian', 'cross_border_transfer'];
const STEPS = ['welcome', 'child', 'consent', 'login'];

const NOW_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: 19 }, (_, i) => NOW_YEAR - i); // this year .. 18y ago
const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);

export default function Start() {
  const navigate = useNavigate();
  const { refreshChildren, setActiveChildId, completeOnboarding, enabledProviders } = useApp();

  const [step, setStep] = useState(0);
  const [name, setName] = useState('');
  const [year, setYear] = useState('');
  const [month, setMonth] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const stepName = STEPS[step];

  const finish = () => {
    completeOnboarding();
    navigate('/ask', { replace: true });
  };

  const saveChild = async () => {
    setError(null);
    if (!year || !month) {
      setError('아이의 출생 연도와 월을 선택해 주세요.');
      return;
    }
    setBusy(true);
    try {
      const child = await api.createChild(name.trim(), toBirthdate(Number(year), Number(month)));
      await refreshChildren();
      setActiveChildId(child.id);
      setStep(2);
    } catch {
      setError('아이 정보를 저장하지 못했어요. 다시 시도해 주세요.');
    } finally {
      setBusy(false);
    }
  };

  const saveConsent = async () => {
    setBusy(true);
    try {
      await api.recordConsents(REQUIRED_CONSENTS);
    } catch {
      /* non-blocking for the pilot */
    } finally {
      setBusy(false);
      setStep(3);
    }
  };

  return (
    <div className="start-screen">
      <div className="start-card">
        <div className="start-progress" aria-hidden="true">
          {STEPS.map((s, i) => (
            <span key={s} className={`start-dot ${i === step ? 'active' : ''} ${i < step ? 'done' : ''}`} />
          ))}
        </div>

        {stepName === 'welcome' && (
          <div className="start-step">
            <div className="start-mark"><Logo size={56} /></div>
            <h1 className="start-title">함께 시작해요</h1>
            <p className="start-sub">
              아이에 맞는 안전한 답변을 드리기 위해, 딱 두 가지만 여쭤볼게요. 30초면 충분해요.
            </p>
            <button className="start-primary" onClick={() => setStep(1)}>
              <span>시작하기</span>
              <ArrowRight size={18} />
            </button>
            <button className="start-skip" onClick={finish}>나중에 할게요</button>
          </div>
        )}

        {stepName === 'child' && (
          <div className="start-step">
            <h1 className="start-title">아이 정보를 알려주세요</h1>
            <p className="start-sub">나이에 맞는 안전 기준(예: 신생아 발열)을 적용하기 위해 필요해요.</p>

            <label className="start-label">아이 이름 <span className="start-optional">(선택)</span></label>
            <input
              className="start-input"
              type="text"
              placeholder="예: 민준이 (비워두셔도 돼요)"
              value={name}
              maxLength={40}
              onChange={(e) => setName(e.target.value)}
            />

            <label className="start-label">태어난 시기</label>
            <div className="start-date-row">
              <select className="start-select" value={year} onChange={(e) => setYear(e.target.value)}>
                <option value="">연도</option>
                {YEARS.map((y) => <option key={y} value={y}>{y}년</option>)}
              </select>
              <select className="start-select" value={month} onChange={(e) => setMonth(e.target.value)}>
                <option value="">월</option>
                {MONTHS.map((m) => <option key={m} value={m}>{m}월</option>)}
              </select>
            </div>

            {error && <p className="start-error">{error}</p>}

            <button className="start-primary" onClick={saveChild} disabled={busy}>
              <span>{busy ? '저장 중…' : '다음'}</span>
              {!busy && <ArrowRight size={18} />}
            </button>
          </div>
        )}

        {stepName === 'consent' && (
          <div className="start-step">
            <div className="start-icon-badge"><ShieldCheck size={26} /></div>
            <h1 className="start-title">개인정보 동의</h1>
            <p className="start-sub">
              안전한 답변을 위해 아이의 건강 정보를 처리해요. 아래 항목에 동의해 주세요.
            </p>
            <ul className="start-consent-list">
              <li>민감정보(건강) 처리 동의</li>
              <li>법정대리인의 아동 개인정보 처리 동의</li>
              <li>국외 이전(의료 출처 검색) 동의</li>
            </ul>
            <label className="start-checkbox">
              <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
              <span>위 필수 항목에 모두 동의합니다.</span>
            </label>
            <button className="start-primary" onClick={saveConsent} disabled={!agreed || busy}>
              <span>{busy ? '처리 중…' : '동의하고 계속'}</span>
              {!busy && <ArrowRight size={18} />}
            </button>
          </div>
        )}

        {stepName === 'login' && (
          <div className="start-step">
            <div className="start-icon-badge"><BadgeCheck size={26} /></div>
            <h1 className="start-title">질문 기록을 저장할까요?</h1>
            <p className="start-sub">
              로그인하면 아이 프로필과 질문 기록이 안전하게 보관돼요. 지금 건너뛰어도 바로 사용할 수 있어요.
            </p>
            {enabledProviders.length > 0 ? (
              <div className="start-login-group">
                {enabledProviders.includes('kakao') && (
                  <a className="start-login start-login-kakao" href={api.loginUrl('kakao')}>
                    <KakaoGlyph size={18} /><span>카카오로 시작하기</span>
                  </a>
                )}
                {enabledProviders.includes('naver') && (
                  <a className="start-login start-login-naver" href={api.loginUrl('naver')}>
                    <NaverGlyph size={18} /><span>네이버로 시작하기</span>
                  </a>
                )}
              </div>
            ) : (
              <p className="start-demo-note">지금은 데모 환경이라 소셜 로그인이 설정되어 있지 않아요.</p>
            )}
            <button className="start-primary start-primary-ghost" onClick={finish}>
              <Check size={18} />
              <span>{enabledProviders.length > 0 ? '나중에 할게요' : '시작하기'}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
