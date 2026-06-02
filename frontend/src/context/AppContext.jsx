import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api } from '../api';

/**
 * App-wide state shared across routes: auth, child profiles, the active child,
 * the conversation list, and the onboarding / free-question flags. Chat streaming
 * state stays local to the Ask page; this holds only what multiple screens need.
 */
const AppContext = createContext(null);

export const useApp = () => useContext(AppContext);

const LS = {
  onboarded: 'pr_onboarded',
  activeChild: 'pr_active_child',
  freeAsk: 'pr_free_ask_used',
};

export function AppProvider({ children }) {
  const [user, setUser] = useState(null);
  const [providers, setProviders] = useState({});
  const [childList, setChildList] = useState([]);
  const [activeChildId, setActiveChildIdState] = useState(() => localStorage.getItem(LS.activeChild));
  const [conversations, setConversations] = useState([]);
  const [hasOnboarded, setHasOnboarded] = useState(() => localStorage.getItem(LS.onboarded) === 'true');
  const [freeAskUsed, setFreeAskUsed] = useState(() => localStorage.getItem(LS.freeAsk) === 'true');
  const [banner, setBanner] = useState(null);

  const refreshAuth = useCallback(async () => {
    try {
      const [me, prov] = await Promise.all([api.getMe(), api.getAuthProviders()]);
      setUser(me);
      setProviders(prov || {});
    } catch {
      /* auth is best-effort; anonymous still works */
    }
  }, []);

  const refreshChildren = useCallback(async () => {
    try {
      const list = await api.listChildren();
      setChildList(list);
      setActiveChildIdState((cur) => {
        if (cur && list.some((c) => c.id === cur)) return cur;
        const next = list[0]?.id ?? null;
        if (next) localStorage.setItem(LS.activeChild, next);
        else localStorage.removeItem(LS.activeChild);
        return next;
      });
    } catch {
      /* ignore — chip falls back to "add child" */
    }
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      setConversations(await api.listConversations());
    } catch {
      setBanner({ text: '대화 목록을 불러오지 못했어요.', retry: refreshConversations });
    }
  }, []);

  useEffect(() => {
    refreshAuth();
    refreshChildren();
    refreshConversations();
  }, [refreshAuth, refreshChildren, refreshConversations]);

  const setActiveChildId = useCallback((id) => {
    setActiveChildIdState(id);
    if (id) localStorage.setItem(LS.activeChild, id);
    else localStorage.removeItem(LS.activeChild);
  }, []);

  const completeOnboarding = useCallback(() => {
    localStorage.setItem(LS.onboarded, 'true');
    setHasOnboarded(true);
  }, []);

  const markFreeAskUsed = useCallback(() => {
    localStorage.setItem(LS.freeAsk, 'true');
    setFreeAskUsed(true);
  }, []);

  const clearFreeAsk = useCallback(() => {
    localStorage.removeItem(LS.freeAsk);
    setFreeAskUsed(false);
  }, []);

  const logout = useCallback(async () => {
    await api.logout();
    await refreshAuth();
  }, [refreshAuth]);

  const activeChild = childList.find((c) => c.id === activeChildId) || null;
  const isAuthenticated = !!user?.authenticated;
  const enabledProviders = Object.keys(providers).filter((p) => providers[p]);

  const value = {
    user,
    isAuthenticated,
    providers,
    enabledProviders,
    refreshAuth,
    logout,
    childList,
    activeChild,
    activeChildId,
    setActiveChildId,
    refreshChildren,
    conversations,
    refreshConversations,
    hasOnboarded,
    completeOnboarding,
    freeAskUsed,
    markFreeAskUsed,
    clearFreeAsk,
    banner,
    setBanner,
  };

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}
