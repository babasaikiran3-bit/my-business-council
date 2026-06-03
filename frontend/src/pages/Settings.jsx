import { useState, useEffect } from 'react';
import { api } from '../api';
import { useApp } from '../context/appContext';
import { ageLabel, childDisplayName, toBirthdate, fromBirthdate } from '../lib/age';
import { Plus, Pencil, Trash, Check, User, LogOut, KakaoGlyph, NaverGlyph } from '../components/Icons';
import './Settings.css';

const NOW_YEAR = new Date().getFullYear();
const YEARS = Array.from({ length: 19 }, (_, i) => NOW_YEAR - i);
const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1);

function ChildForm({ initial, onCancel, onSubmit }) {
  const init = fromBirthdate(initial?.birthdate);
  const [name, setName] = useState(initial?.name || '');
  const [year, setYear] = useState(init.year || '');
  const [month, setMonth] = useState(init.month || '');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!year || !month) return;
    setBusy(true);
    try {
      await onSubmit({ name: name.trim(), birthdate: toBirthdate(Number(year), Number(month)) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="child-form">
      <input
        className="settings-input"
        type="text"
        placeholder="아이 이름 (선택)"
        value={name}
        maxLength={40}
        onChange={(e) => setName(e.target.value)}
      />
      <div className="child-form-date">
        <select className="settings-input" value={year} onChange={(e) => setYear(e.target.value)}>
          <option value="">연도</option>
          {YEARS.map((y) => <option key={y} value={y}>{y}년</option>)}
        </select>
        <select className="settings-input" value={month} onChange={(e) => setMonth(e.target.value)}>
          <option value="">월</option>
          {MONTHS.map((m) => <option key={m} value={m}>{m}월</option>)}
        </select>
      </div>
      <div className="child-form-actions">
        <button className="settings-btn-ghost" onClick={onCancel} disabled={busy}>취소</button>
        <button className="settings-btn-primary" onClick={submit} disabled={!year || !month || busy}>
          {busy ? '저장 중…' : '저장'}
        </button>
      </div>
    </div>
  );
}

export default function Settings() {
  const {
    childList, activeChildId, setActiveChildId, refreshChildren,
    user, isAuthenticated, enabledProviders, logout,
    conversations, refreshConversations,
  } = useApp();

  const [editing, setEditing] = useState(null); // child id | 'new' | null
  const [consents, setConsents] = useState(null);
  const [confirmDeleteData, setConfirmDeleteData] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.getConsents().then((c) => { if (!cancelled) setConsents(c); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const addChild = async ({ name, birthdate }) => {
    const child = await api.createChild(name, birthdate);
    await refreshChildren();
    setActiveChildId(child.id);
    setEditing(null);
  };

  const saveChild = async (id, { name, birthdate }) => {
    await api.updateChild(id, { name, birthdate });
    await refreshChildren();
    setEditing(null);
  };

  const removeChild = async (id) => {
    await api.deleteChild(id);
    await refreshChildren();
  };

  const deleteAllConversations = async () => {
    await Promise.all(conversations.map((c) => api.deleteConversation(c.id)));
    await refreshConversations();
    setConfirmDeleteData(false);
  };

  return (
    <div className="settings-page">
      <div className="settings-container">
        <h1 className="settings-h1">설정</h1>

        {/* Child profiles */}
        <section className="settings-section">
          <h2 className="settings-h2">아이 프로필</h2>
          <div className="settings-card">
            {childList.length === 0 && editing !== 'new' && (
              <p className="settings-empty">아직 등록된 아이가 없어요.</p>
            )}

            {childList.map((child) => (
              <div key={child.id} className="child-row">
                {editing === child.id ? (
                  <ChildForm
                    initial={child}
                    onCancel={() => setEditing(null)}
                    onSubmit={(fields) => saveChild(child.id, fields)}
                  />
                ) : (
                  <>
                    <button
                      className={`child-select ${child.id === activeChildId ? 'active' : ''}`}
                      onClick={() => setActiveChildId(child.id)}
                    >
                      <span className="child-avatar">{childDisplayName(child).slice(0, 1)}</span>
                      <span className="child-info">
                        <span className="child-name">{childDisplayName(child)}</span>
                        <span className="child-age">{ageLabel(child.birthdate)}</span>
                      </span>
                      {child.id === activeChildId && <span className="child-active-badge"><Check size={15} /></span>}
                    </button>
                    <div className="child-actions">
                      <button className="icon-btn" onClick={() => setEditing(child.id)} aria-label="수정"><Pencil size={16} /></button>
                      <button className="icon-btn icon-btn-danger" onClick={() => removeChild(child.id)} aria-label="삭제"><Trash size={16} /></button>
                    </div>
                  </>
                )}
              </div>
            ))}

            {editing === 'new' ? (
              <ChildForm onCancel={() => setEditing(null)} onSubmit={addChild} />
            ) : (
              <button className="settings-add" onClick={() => setEditing('new')}>
                <Plus size={17} /><span>아이 추가</span>
              </button>
            )}
          </div>
        </section>

        {/* Account */}
        <section className="settings-section">
          <h2 className="settings-h2">계정</h2>
          <div className="settings-card">
            {isAuthenticated ? (
              <div className="account-block">
                <span className="child-avatar"><User size={18} /></span>
                <div className="child-info">
                  <span className="child-name">{user?.display_name || '내 계정'}</span>
                  <span className="child-age">{(user?.providers || []).join(', ') || '로그인됨'}</span>
                </div>
                <button className="settings-btn-ghost" onClick={logout}>
                  <LogOut size={15} /><span>로그아웃</span>
                </button>
              </div>
            ) : enabledProviders.length > 0 ? (
              <div className="settings-login-group">
                {enabledProviders.includes('kakao') && (
                  <a className="settings-login settings-login-kakao" href={api.loginUrl('kakao')}>
                    <KakaoGlyph size={18} /><span>카카오로 로그인</span>
                  </a>
                )}
                {enabledProviders.includes('naver') && (
                  <a className="settings-login settings-login-naver" href={api.loginUrl('naver')}>
                    <NaverGlyph size={18} /><span>네이버로 로그인</span>
                  </a>
                )}
              </div>
            ) : (
              <p className="settings-empty">지금은 로그인 없이 사용 중이에요. 소셜 로그인은 준비 중이에요.</p>
            )}
          </div>
        </section>

        {/* Consents */}
        <section className="settings-section">
          <h2 className="settings-h2">개인정보 동의</h2>
          <div className="settings-card">
            {consents?.has_required ? (
              <p className="settings-consent-ok"><Check size={16} /> 필수 항목에 동의하셨어요.</p>
            ) : (
              <p className="settings-empty">아직 필수 동의가 완료되지 않았어요.</p>
            )}
            <p className="settings-note">건강 정보는 답변 생성에만 사용되며, 신뢰할 수 있는 의료 출처 검색을 위해 처리돼요.</p>
          </div>
        </section>

        {/* Data */}
        <section className="settings-section">
          <h2 className="settings-h2">데이터</h2>
          <div className="settings-card">
            {confirmDeleteData ? (
              <div className="settings-confirm">
                <p>모든 대화 기록을 삭제할까요? 되돌릴 수 없어요.</p>
                <div className="child-form-actions">
                  <button className="settings-btn-ghost" onClick={() => setConfirmDeleteData(false)}>취소</button>
                  <button className="settings-btn-danger" onClick={deleteAllConversations}>삭제</button>
                </div>
              </div>
            ) : (
              <button className="settings-row-btn settings-row-btn-danger" onClick={() => setConfirmDeleteData(true)} disabled={conversations.length === 0}>
                <Trash size={16} /><span>대화 기록 전체 삭제 ({conversations.length})</span>
              </button>
            )}
            <p className="settings-note settings-note-muted">계정 삭제는 곧 제공될 예정이에요.</p>
          </div>
        </section>

        {/* About */}
        <section className="settings-section">
          <h2 className="settings-h2">정보</h2>
          <div className="settings-card">
            <p className="settings-note">
              부모 라운드테이블은 신뢰할 수 있는 의료 출처를 바탕으로 한 일반 정보를 제공하며,
              의학적 진단이나 전문적인 진료를 대신하지 않습니다. 위급한 상황에서는 119 또는 주치의에게
              바로 연락하세요.
            </p>
            <p className="settings-note settings-note-muted">버전 0.1.0 · 파일럿</p>
          </div>
        </section>
      </div>
    </div>
  );
}
