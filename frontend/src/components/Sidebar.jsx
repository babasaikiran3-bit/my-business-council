import './Sidebar.css';
import {
  Logo,
  Plus,
  User,
  LogOut,
  Close,
  KakaoGlyph,
  NaverGlyph,
  MessageHeart,
} from './Icons';

const PROVIDERS = {
  kakao: { label: '카카오로 시작하기', Glyph: KakaoGlyph },
  naver: { label: '네이버로 시작하기', Glyph: NaverGlyph },
};

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  user,
  providers = {},
  onLogin,
  onLogout,
  open = false,
  onClose,
}) {
  const enabledProviders = Object.keys(PROVIDERS).filter((p) => providers[p]);

  return (
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <Logo size={34} />
          <div className="sidebar-brand-text">
            <span className="sidebar-brand-name">부모 라운드테이블</span>
            <span className="sidebar-brand-tag">믿을 수 있는 육아 답변</span>
          </div>
          <button
            className="sidebar-close"
            onClick={onClose}
            aria-label="메뉴 닫기"
          >
            <Close size={20} />
          </button>
        </div>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          <Plus size={18} />
          <span>새 질문하기</span>
        </button>
      </div>

      <div className="conversation-list">
        {conversations.length === 0 ? (
          <div className="no-conversations">
            <MessageHeart size={28} />
            <p>아직 질문이 없어요.</p>
            <span>위 버튼으로 첫 질문을 시작해 보세요.</span>
          </div>
        ) : (
          conversations.map((conv) => (
            <button
              key={conv.id}
              className={`conversation-item ${
                conv.id === currentConversationId ? 'active' : ''
              }`}
              onClick={() => onSelectConversation(conv.id)}
            >
              <span className="conversation-title">
                {conv.title || '새 질문'}
              </span>
              <span className="conversation-meta">
                메시지 {conv.message_count}개
              </span>
            </button>
          ))
        )}
      </div>

      <div className="sidebar-account">
        {user?.authenticated ? (
          <div className="account-row">
            <span className="account-avatar" aria-hidden="true">
              <User size={18} />
            </span>
            <span className="account-name">{user.display_name || '내 계정'}</span>
            <button
              className="account-logout"
              onClick={onLogout}
              aria-label="로그아웃"
            >
              <LogOut size={17} />
            </button>
          </div>
        ) : enabledProviders.length > 0 ? (
          <div className="account-login-group">
            {enabledProviders.map((p) => {
              const { label, Glyph } = PROVIDERS[p];
              return (
                <button
                  key={p}
                  className={`account-login account-login-${p}`}
                  onClick={() => onLogin(p)}
                >
                  <Glyph size={18} />
                  <span>{label}</span>
                </button>
              );
            })}
            <p className="account-login-note">
              로그인하면 아이 프로필과 질문 기록이 안전하게 저장돼요.
            </p>
          </div>
        ) : (
          <div className="account-hint">
            지금은 로그인 없이 사용 중이에요. 카카오 로그인은 곧 제공돼요.
          </div>
        )}
      </div>
    </aside>
  );
}
