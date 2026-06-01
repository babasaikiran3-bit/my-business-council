import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { Logo, Menu } from './components/Icons';
import { api } from './api';
import './App.css';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [user, setUser] = useState(null);
  const [providers, setProviders] = useState({});
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // Transient, dismissible banner for background failures (network / auth / login).
  // Initialised from the URL so a ?login=error redirect shows a banner without a
  // synchronous setState inside the mount effect.
  const [banner, setBanner] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('login') === 'error'
      ? { text: '로그인에 실패했어요. 다시 시도해 주세요.' }
      : null;
  });
  // Remembers the last send so the error state can offer a retry.
  const [lastSend, setLastSend] = useState(null);

  const loadConversations = async () => {
    try {
      setConversations(await api.listConversations());
    } catch (error) {
      console.error('Failed to load conversations:', error);
      setBanner({ text: '대화 목록을 불러오지 못했어요.', retry: loadConversations });
    }
  };

  const loadConversation = async (id) => {
    try {
      setCurrentConversation(await api.getConversation(id));
    } catch (error) {
      console.error('Failed to load conversation:', error);
      setBanner({ text: '대화를 불러오지 못했어요.', retry: () => loadConversation(id) });
    }
  };

  const loadAuth = async () => {
    try {
      const [me, prov] = await Promise.all([api.getMe(), api.getAuthProviders()]);
      setUser(me);
      setProviders(prov);
    } catch (error) {
      console.error('Failed to load auth:', error);
    }
  };

  // Load conversations + auth state on mount
  useEffect(() => {
    loadConversations();
    loadAuth();
    // After an OAuth redirect (?login=ok|error), clean the URL. The error banner is
    // initialised from the URL in useState above (no setState inside this effect).
    const params = new URLSearchParams(window.location.search);
    if (params.has('login')) {
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  // Load conversation details when selected
  useEffect(() => {
    if (currentConversationId) {
      loadConversation(currentConversationId);
    }
  }, [currentConversationId]);

  const handleLogin = (provider) => {
    window.location.href = api.loginUrl(provider);
  };

  const handleLogout = async () => {
    await api.logout();
    await loadAuth();
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([
        { id: newConv.id, created_at: newConv.created_at, message_count: 0 },
        ...conversations,
      ]);
      setCurrentConversationId(newConv.id);
      setSidebarOpen(false);
    } catch (error) {
      console.error('Failed to create conversation:', error);
      setBanner({ text: '새 대화를 시작하지 못했어요.' });
    }
  };

  const handleSelectConversation = (id) => {
    setCurrentConversationId(id);
    setSidebarOpen(false);
  };

  // The streaming reducer: progressively fills the trailing assistant message.
  const handleStreamEvent = (eventType, event) => {
    const patchLast = (fn) =>
      setCurrentConversation((prev) => {
        if (!prev) return prev;
        const messages = [...prev.messages];
        const lastMsg = messages[messages.length - 1];
        if (lastMsg) fn(lastMsg);
        return { ...prev, messages };
      });

    switch (eventType) {
      case 'emergency':
        patchLast((m) => { m.emergency = event.data; });
        break;
      case 'stage0_start':
        patchLast((m) => { m.loading.stage0 = true; });
        break;
      case 'stage0_complete':
        patchLast((m) => { m.stage0 = event.data; m.loading.stage0 = false; });
        break;
      case 'stage1_start':
        patchLast((m) => { m.loading.stage1 = true; });
        break;
      case 'stage1_complete':
        patchLast((m) => { m.stage1 = event.data; m.loading.stage1 = false; });
        break;
      case 'stage2_start':
        patchLast((m) => { m.loading.stage2 = true; });
        break;
      case 'stage2_complete':
        patchLast((m) => { m.stage2 = event.data; m.metadata = event.metadata; m.loading.stage2 = false; });
        break;
      case 'stage3_start':
        patchLast((m) => { m.loading.stage3 = true; });
        break;
      case 'stage3_complete':
        patchLast((m) => { m.stage3 = event.data; m.loading.stage3 = false; });
        break;
      case 'title_complete':
        loadConversations();
        break;
      case 'complete':
        loadConversations();
        setIsLoading(false);
        break;
      case 'error':
        patchLast((m) => { if (m.role === 'assistant') m.error = event.message || true; });
        setIsLoading(false);
        break;
      default:
        console.log('Unknown event type:', eventType);
    }
  };

  // Adds a fresh assistant placeholder and streams into it. Used by both the initial
  // send and retry (retry does NOT re-add the user message).
  const streamAssistant = async (convId, content, ageDays) => {
    setIsLoading(true);
    setLastSend({ convId, content, ageDays });

    const assistantMessage = {
      role: 'assistant',
      emergency: null,
      stage0: null, stage1: null, stage2: null, stage3: null,
      metadata: null,
      loading: { stage0: false, stage1: false, stage2: false, stage3: false },
    };
    setCurrentConversation((prev) => ({ ...prev, messages: [...prev.messages, assistantMessage] }));

    // Fresh idempotency key per attempt: a retry must re-run, not replay a stored partial.
    const idempotencyKey =
      (window.crypto && window.crypto.randomUUID && window.crypto.randomUUID()) ||
      `${Date.now()}-${Math.random()}`;

    try {
      await api.sendMessageStream(convId, content, ageDays, handleStreamEvent, { idempotencyKey });
    } catch (error) {
      console.error('Failed to send message:', error);
      // Non-destructive: keep the user's message, mark the assistant as failed.
      setCurrentConversation((prev) => {
        if (!prev) return prev;
        const messages = [...prev.messages];
        const lastMsg = messages[messages.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') lastMsg.error = true;
        return { ...prev, messages };
      });
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (content, ageDays) => {
    if (isLoading) return; // defense-in-depth double-send guard (ChatInterface also guards)

    let convId = currentConversationId;
    if (!convId) {
      try {
        const newConv = await api.createConversation();
        convId = newConv.id;
        setConversations((prev) => [
          { id: newConv.id, created_at: newConv.created_at, message_count: 0 },
          ...prev,
        ]);
        setCurrentConversationId(newConv.id);
        setCurrentConversation({ id: newConv.id, messages: [] });
      } catch (error) {
        console.error('Failed to create conversation:', error);
        setBanner({ text: '대화를 시작하지 못했어요. 다시 시도해 주세요.' });
        return;
      }
    }

    // Optimistically add the user's message (kept even if the answer fails).
    setCurrentConversation((prev) => ({
      ...prev,
      messages: [...prev.messages, { role: 'user', content }],
    }));

    await streamAssistant(convId, content, ageDays);
  };

  const handleRetry = async () => {
    if (!lastSend || isLoading) return;
    // Drop the failed assistant placeholder, then stream a fresh attempt.
    setCurrentConversation((prev) => {
      if (!prev) return prev;
      const messages = [...prev.messages];
      if (messages.length && messages[messages.length - 1].role === 'assistant') messages.pop();
      return { ...prev, messages };
    });
    await streamAssistant(lastSend.convId, lastSend.content, lastSend.ageDays);
  };

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        user={user}
        providers={providers}
        onLogin={handleLogin}
        onLogout={handleLogout}
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
          <button
            className="icon-button"
            onClick={() => setSidebarOpen(true)}
            aria-label="메뉴 열기"
          >
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
                <button
                  type="button"
                  onClick={() => { const r = banner.retry; setBanner(null); r(); }}
                >
                  다시 시도
                </button>
              )}
              <button type="button" onClick={() => setBanner(null)} aria-label="닫기">✕</button>
            </span>
          </div>
        )}
        <ChatInterface
          conversation={currentConversation}
          onSendMessage={handleSendMessage}
          onRetry={handleRetry}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}

export default App;
