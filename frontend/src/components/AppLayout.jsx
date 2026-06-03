import { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import Sidebar from './Sidebar';
import BottomTabBar from './BottomTabBar';
import { Logo, Menu } from './Icons';
import { api } from '../api';
import { useApp } from '../context/appContext';
import '../App.css';

/**
 * The signed-in app shell for /ask and /settings: persistent sidebar on desktop,
 * drawer + bottom tabs on mobile, with the transient error banner.
 */
export default function AppLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const { conversations, user, providers, logout, banner, setBanner } = useApp();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const match = location.pathname.match(/^\/ask\/(.+)$/);
  const activeConversationId = match ? match[1] : null;

  const go = (path) => { navigate(path); setSidebarOpen(false); };

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={activeConversationId}
        onSelectConversation={(id) => go(`/ask/${id}`)}
        onNewConversation={() => go('/ask')}
        user={user}
        providers={providers}
        onLogin={(p) => { window.location.href = api.loginUrl(p); }}
        onLogout={logout}
        onOpenSettings={() => go('/settings')}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <div
        className={`sidebar-backdrop ${sidebarOpen ? 'show' : ''}`}
        onClick={() => setSidebarOpen(false)}
        aria-hidden="true"
      />
      <div className="main-col">
        <div className="mobile-topbar">
          <button className="icon-button" onClick={() => setSidebarOpen(true)} aria-label="메뉴 열기">
            <Menu size={22} />
          </button>
          <div className="mobile-topbar-brand">
            <Logo size={28} />
            <span>부모 라운드테이블</span>
          </div>
        </div>

        {banner && (
          <div className="app-banner" role="alert">
            <span>{banner.text}</span>
            <span className="app-banner-actions">
              {banner.retry && (
                <button type="button" onClick={() => { const r = banner.retry; setBanner(null); r(); }}>
                  다시 시도
                </button>
              )}
              <button type="button" onClick={() => setBanner(null)} aria-label="닫기">✕</button>
            </span>
          </div>
        )}

        <Outlet />
        <BottomTabBar onOpenHistory={() => setSidebarOpen(true)} />
      </div>
    </div>
  );
}
