/**
 * API client for the Parenting Roundtable backend.
 */

const API_BASE = 'http://localhost:8001';

export const api = {
  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      credentials: 'include',
    });
    if (!response.ok) {
      throw new Error('Failed to list conversations');
    }
    return response.json();
  },

  /**
   * Create a new conversation.
   */
  async createConversation() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      throw new Error('Failed to create conversation');
    }
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`,
      { credentials: 'include' }
    );
    if (!response.ok) {
      throw new Error('Failed to get conversation');
    }
    return response.json();
  },

  /**
   * Send a message in a conversation.
   */
  async sendMessage(conversationId, content) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
      }
    );
    if (!response.ok) {
      throw new Error('Failed to send message');
    }
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {number|null} ageDays - The child's age in days (typed; drives safety triage)
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, ageDays, onEvent) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content, age_days: ageDays }),
      }
    );

    if (!response.ok) {
      throw new Error('Failed to send message');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, birthdate }),
    });
    if (!r.ok) throw new Error('Failed to create child');
    return r.json();
  },

  async deleteChild(childId) {
    await fetch(`${API_BASE}/api/children/${childId}`, {
      method: 'DELETE',
      credentials: 'include',
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
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kinds, version }),
    });
    return r.ok ? r.json() : null;
  },
};
