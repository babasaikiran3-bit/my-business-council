/**
 * API client for the LLM Council backend.
 */

const API_BASE = 'http://localhost:8001';

export const api = {
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`);
    if (!response.ok) throw new Error('Failed to list conversations');
    return response.json();
  },

  async createConversation() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (!response.ok) throw new Error('Failed to create conversation');
    return response.json();
  },

  async getConversation(conversationId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}`);
    if (!response.ok) throw new Error('Failed to get conversation');
    return response.json();
  },

  async deleteConversation(conversationId) {
    const response = await fetch(`${API_BASE}/api/conversations/${conversationId}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete conversation');
    return response.json();
  },

  /** Repos autodetectados para el selector. */
  async fetchRepos() {
    const response = await fetch(`${API_BASE}/api/repos`);
    if (!response.ok) throw new Error('Failed to fetch repos');
    return response.json(); // { repos: [{name, path}] }
  },

  /** Universo de modelos + salud + activos. */
  async fetchModels() {
    const response = await fetch(`${API_BASE}/api/models`);
    if (!response.ok) throw new Error('Failed to fetch models');
    return response.json(); // { chairman, members, models: [...] }
  },

  /** Guarda la config del consejo (members + chairman). */
  async saveCouncilConfig(members, chairman) {
    const response = await fetch(`${API_BASE}/api/council/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ members, chairman }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to save council config');
    }
    return response.json();
  },

  /**
   * Envía un mensaje y recibe eventos en vivo (SSE).
   * @param {object} opts - { conversationId, content, repoPath, members, chairman }
   * @param {function} onEvent - (event) => void  (event.type es el discriminador)
   */
  /** PREVIEW: el chairman genera el documento (no escribe). Devuelve {path, content, model}. */
  async previewConsensus(conversationId, repoPath) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/document-consensus`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_path: repoPath }),
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to preview consensus');
    }
    return response.json(); // { path, content, model, repo_path }
  },

  /** APROBAR: el backend escribe el documento pendiente. Devuelve {consensus_file}. */
  async approveConsensus(conversationId, repoPath) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/document-consensus/approve`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_path: repoPath }),
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to approve consensus');
    }
    return response.json(); // { consensus_file }
  },

  /** DESCARTAR: tira el borrador pendiente. */
  async discardConsensus(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/document-consensus/discard`,
      { method: 'POST' }
    );
    if (!response.ok) throw new Error('Failed to discard consensus');
    return response.json();
  },

  async streamMessage({ conversationId, content, repoPath, members, chairman, research }, onEvent) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content,
          repo_path: repoPath || null,
          members: members || null,
          chairman: chairman || null,
          research: research !== false,
        }),
      }
    );
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to send message');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      // Procesar mensajes SSE completos (separados por línea en blanco o salto)
      let idx;
      while ((idx = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 1);
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();
          if (!data) continue;
          try {
            onEvent(JSON.parse(data));
          } catch (e) {
            console.error('Failed to parse SSE event:', e, data);
          }
        }
      }
    }
  },
};
