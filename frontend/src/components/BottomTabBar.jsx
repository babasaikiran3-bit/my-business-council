import { useLocation, useNavigate } from 'react-router-dom';
import { Home, BookOpen, Settings } from './Icons';
import './BottomTabBar.css';

/**
 * Mobile-only bottom navigation (홈 / 기록 / 설정). Hidden on desktop ≥900px where the
 * sidebar is always present. "기록" opens the conversation drawer (the sidebar).
 */
export default function BottomTabBar({ onOpenHistory }) {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const onAsk = pathname.startsWith('/ask');
  const onSettings = pathname.startsWith('/settings');

  return (
    <nav className="bottom-tabs" aria-label="주요 메뉴">
      <button
        type="button"
        className={`bottom-tab ${onAsk ? 'active' : ''}`}
        onClick={() => navigate('/ask')}
      >
        <Home size={22} />
        <span>홈</span>
      </button>
      <button type="button" className="bottom-tab" onClick={onOpenHistory}>
        <BookOpen size={22} />
        <span>기록</span>
      </button>
      <button
        type="button"
        className={`bottom-tab ${onSettings ? 'active' : ''}`}
        onClick={() => navigate('/settings')}
      >
        <Settings size={22} />
        <span>설정</span>
      </button>
    </nav>
  );
}
