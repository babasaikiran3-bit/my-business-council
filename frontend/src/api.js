/**
 * API client for the Parenting Roundtable backend.
 */

// Env-driven so a production build (Vercel/Netlify) can target the real backend.
// Falls back to localhost for dev. Set VITE_API_BASE at build time in production.
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001';

// Custom header required by the backend on every state-changing request. A cross-site
// attacker page cannot set it without a CORS preflight the strict allowlist rejects,
// so it is our CSRF defense under the SameSite=None cross-site cookie topology.
const CSRF_HEADERS = { 'X-Requested-With': 'parenting-roundtable' };
const JSON_HEADERS = { 'Content-Type': 'application/json', ...CSRF_HEADERS };

// Abort a stalled stream after this long with no new event (slow/mobile networks).
const STREAM_TIMEOUT_MS = 180000;

export const api = {
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`, { credentials: 'include' });
    if (!response.ok) throw new Error('Failed to list conversations');
    return response.json();
  },

  async createConversation() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      credentials: 'include',
      headers: JSON_HEADERS,
      body: JSON.stringify({}),
    });
    if (!response.ok) throw new Error('Failed to create conversation');
    return response.json();
  },

  async getConversation(conversationId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}`, {
      credentials: 'include',
    });
    if (!response.ok) throw new Error('Failed to get conversation');
    return response.json();
  },

  async deleteConversation(conversationId) {
    await fetch(`${API_BASE}/api/conversations/${conversationId}`, {
      method: 'DELETE',
      credentials: 'include',
      headers: CSRF_HEADERS,
    });
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId
   * @param {string} content
   * @param {number|null} ageDays - typed age in days (drives safety triage)
   * @param {function} onEvent - (eventType, event) => void
   * @param {{idempotencyKey?: string}} [opts]
   */
  async sendMessageStream(conversationId, content, ageDays, onEvent, opts = {}) {
    const controller = new AbortController();
    let timer = setTimeout(() => controller.abort(), STREAM_TIMEOUT_MS);
    const resetTimer = () => {
      clearTimeout(timer);
      timer = setTimeout(() => controller.abort(), STREAM_TIMEOUT_MS);
    };

    const emitData = (line) => {
      if (!line.startsWith('data: ')) return;
      try {
        const event = JSON.parse(line.slice(6));
        onEvent(event.type, event);
      } catch (e) {
        console.error('Failed to parse SSE event:', e);
      }
    };

    try {
      const response = await fetch(
        `${API_BASE}/api/conversations/${conversationId}/message/stream`,
        {
          method: 'POST',
          credentials: 'include',
          headers: JSON_HEADERS,
          body: JSON.stringify({
            content,
            age_days: ageDays,
            idempotency_key: opts.idempotencyKey,
          }),
          signal: controller.signal,
        }
      );

      if (!response.ok) {
        onEvent('error', { type: 'error', message: `서버 오류가 발생했어요 (${response.status}).` });
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      // Buffer across reader chunks: an SSE event split over two TCP frames must not be
      // dropped. Keep the trailing partial line until its newline arrives.
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        resetTimer();
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) emitData(line);
      }
      if (buffer) emitData(buffer); // flush a final newline-less event
    } catch (err) {
      const message =
        err.name === 'AbortError'
          ? '응답이 지연되어 중단했어요. 잠시 후 다시 시도해 주세요.'
          : '네트워크 오류가 발생했어요. 연결을 확인하고 다시 시도해 주세요.';
      onEvent('error', { type: 'error', message });
    } finally {
      clearTimeout(timer);
    }
  },

  // --- Phase 2: identity, child profiles, consent ---

  async getAuthProviders() {
    const r = await fetch(`${API_BASE}/api/auth/providers`, { credentials: 'include' });
    return r.ok ? r.json() : {};
  },

  async getMe() {
    const r = await fetch(`${API_BASE}/api/auth/me`, { credentials: 'include' });
    return r.ok ? r.json() : null;
  },

  loginUrl(provider) {
    return `${API_BASE}/api/auth/${provider}/login`;
  },

  async logout() {
    await fetch(`${API_BASE}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include',
      headers: CSRF_HEADERS,
    });
  },

  async listChildren() {
    const r = await fetch(`${API_BASE}/api/children`, { credentials: 'include' });
    return r.ok ? r.json() : [];
  },

  async createChild(name, birthdate) {
    const r = await fetch(`${API_BASE}/api/children`, {
      method: 'POST',
      credentials: 'include',
      headers: JSON_HEADERS,
      body: JSON.stringify({ name, birthdate }),
    });
    if (!r.ok) throw new Error('Failed to create child');
    return r.json();
  },

  async deleteChild(childId) {
    await fetch(`${API_BASE}/api/children/${childId}`, {
      method: 'DELETE',
      credentials: 'include',
      headers: CSRF_HEADERS,
    });
  },

  async getConsents() {
    const r = await fetch(`${API_BASE}/api/consents`, { credentials: 'include' });
    return r.ok ? r.json() : null;
  },

  async recordConsents(kinds, version = '1.0') {
    const r = await fetch(`${API_BASE}/api/consents`, {
      method: 'POST',
      credentials: 'include',
      headers: JSON_HEADERS,
      body: JSON.stringify({ kinds, version }),
    });
    return r.ok ? r.json() : null;
  },
};
