import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../api';
import { useApp } from '../context/appContext';
import ChatInterface from '../components/ChatInterface';
import LoginWall from '../components/LoginWall';

/**
 * The Ask (home) screen. Owns the per-conversation streaming state; shared state
 * (children, conversations, auth) comes from AppContext. Single-turn: the composer
 * shows on the welcome state; a finished answer offers "다른 질문 하기" (new conversation).
 */
export default function Ask() {
  const { id: routeId } = useParams();
  const navigate = useNavigate();
  const {
    activeChild, refreshConversations, isAuthenticated, freeAskUsed, markFreeAskUsed, setBanner,
  } = useApp();

  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [lastSend, setLastSend] = useState(null);
  const ownedIdRef = useRef(null); // a conversation we hold in memory (don't reload over it)

  useEffect(() => {
    let cancelled = false;
    if (!routeId) {
      ownedIdRef.current = null;
      queueMicrotask(() => {
        if (!cancelled) setCurrentConversation(null);
      });
      return;
    }
    if (ownedIdRef.current === routeId) return; // just created / streaming — keep memory state
    (async () => {
      try {
        const c = await api.getConversation(routeId);
        if (!cancelled) {
          setCurrentConversation(c);
          ownedIdRef.current = routeId;
        }
      } catch {
        if (!cancelled) setBanner({ text: '대화를 불러오지 못했어요.' });
      }
    })();
    return () => { cancelled = true; };
  }, [routeId]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleStreamEvent = useCallback((eventType, event) => {
    const patchLast = (fn) => setCurrentConversation((prev) => {
      if (!prev) return prev;
      const messages = [...prev.messages];
      const lastMsg = messages[messages.length - 1];
      if (lastMsg) fn(lastMsg);
      return { ...prev, messages };
    });
    switch (eventType) {
      case 'emergency': patchLast((m) => { m.emergency = event.data; }); break;
      case 'stage0_start': patchLast((m) => { m.loading.stage0 = true; }); break;
      case 'stage0_complete': patchLast((m) => { m.stage0 = event.data; m.loading.stage0 = false; }); break;
      case 'stage1_start': patchLast((m) => { m.loading.stage1 = true; }); break;
      case 'stage1_complete': patchLast((m) => { m.stage1 = event.data; m.loading.stage1 = false; }); break;
      case 'stage2_start': patchLast((m) => { m.loading.stage2 = true; }); break;
      case 'stage2_complete': patchLast((m) => { m.stage2 = event.data; m.metadata = event.metadata; m.loading.stage2 = false; }); break;
      case 'stage3_start': patchLast((m) => { m.loading.stage3 = true; }); break;
      case 'stage3_complete': patchLast((m) => { m.stage3 = event.data; m.loading.stage3 = false; }); break;
      case 'title_complete': refreshConversations(); break;
      case 'complete':
        refreshConversations();
        setIsLoading(false);
        if (!isAuthenticated) markFreeAskUsed(); // free question consumed
        break;
      case 'error':
        patchLast((m) => { if (m.role === 'assistant') m.error = event.message || true; });
        setIsLoading(false);
        break;
      default: break;
    }
  }, [refreshConversations, isAuthenticated, markFreeAskUsed]);

  const streamAssistant = useCallback(async (convId, content) => {
    setIsLoading(true);
    setLastSend({ convId, content });
    const assistant = {
      role: 'assistant', emergency: null, stage0: null, stage1: null, stage2: null,
      stage3: null, metadata: null, loading: { stage0: false, stage1: false, stage2: false, stage3: false },
    };
    setCurrentConversation((prev) => ({ ...prev, messages: [...prev.messages, assistant] }));
    const idem = window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
    try {
      await api.sendMessageStream(convId, content, activeChild?.age_days ?? null, handleStreamEvent, {
        idempotencyKey: idem,
        childProfileId: activeChild?.id ?? null,
      });
    } catch {
      setCurrentConversation((prev) => {
        if (!prev) return prev;
        const messages = [...prev.messages];
        const l = messages[messages.length - 1];
        if (l && l.role === 'assistant') l.error = true;
        return { ...prev, messages };
      });
      setIsLoading(false);
    }
  }, [activeChild, handleStreamEvent]);

  const handleSendMessage = useCallback(async (content) => {
    if (isLoading) return;
    let convId = routeId;
    if (!convId) {
      try {
        const newConv = await api.createConversation();
        convId = newConv.id;
        ownedIdRef.current = convId; // claim before navigate so the load effect skips it
        setCurrentConversation({ id: convId, messages: [] });
        navigate(`/ask/${convId}`, { replace: true });
      } catch {
        setBanner({ text: '대화를 시작하지 못했어요. 다시 시도해 주세요.' });
        return;
      }
    }
    setCurrentConversation((prev) => ({
      ...prev,
      messages: [...(prev?.messages || []), { role: 'user', content }],
    }));
    await streamAssistant(convId, content);
  }, [isLoading, routeId, navigate, streamAssistant, setBanner]);

  const handleRetry = useCallback(async () => {
    if (!lastSend || isLoading) return;
    setCurrentConversation((prev) => {
      if (!prev) return prev;
      const messages = [...prev.messages];
      if (messages.length && messages[messages.length - 1].role === 'assistant') messages.pop();
      return { ...prev, messages };
    });
    await streamAssistant(lastSend.convId, lastSend.content);
  }, [lastSend, isLoading, streamAssistant]);

  const handleNewQuestion = () => navigate('/ask');
  const handleEditChild = () => navigate('/settings');

  // Decision 1: anonymous users get exactly one free question, then the login wall.
  const composerLocked = !isAuthenticated && freeAskUsed && !routeId;

  return (
    <ChatInterface
      conversation={currentConversation}
      onSendMessage={handleSendMessage}
      onRetry={handleRetry}
      onNewQuestion={handleNewQuestion}
      isLoading={isLoading}
      activeChild={activeChild}
      onEditChild={handleEditChild}
      composerLocked={composerLocked}
      lockedNode={<LoginWall />}
    />
  );
}
