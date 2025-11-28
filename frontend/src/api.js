/**
 * API client for the LLM Council backend.
 */

const API_BASE = 'http://localhost:8001';

export const api = {
  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`);
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
      `${API_BASE}/api/conversations/${conversationId}`
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
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content }),
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

  /**
   * GitHub Integration
   */

  /**
   * List all GitHub repositories for the authenticated user.
   */
  async listGithubRepos() {
    const response = await fetch(`${API_BASE}/api/github/repos`);
    if (!response.ok) {
      if (response.status === 503) {
        // GitHub not configured
        return { repos: [], error: 'GitHub integration not configured' };
      }
      throw new Error('Failed to list GitHub repos');
    }
    return response.json();
  },

  /**
   * Attach a GitHub repository to a conversation.
   */
  async attachRepo(conversationId, repoFullName) {
    const encodedRepo = encodeURIComponent(repoFullName);
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/repos/${encodedRepo}`,
      {
        method: 'POST',
      }
    );
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to attach repository');
    }
    return response.json();
  },

  /**
   * List repositories attached to a conversation.
   */
  async listConversationRepos(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/repos`
    );
    if (!response.ok) {
      throw new Error('Failed to list conversation repos');
    }
    return response.json();
  },

  /**
   * Detach a repository from a conversation.
   */
  async detachRepo(conversationId, repoFullName) {
    const encodedRepo = encodeURIComponent(repoFullName);
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/repos/${encodedRepo}`,
      {
        method: 'DELETE',
      }
    );
    if (!response.ok) {
      throw new Error('Failed to detach repository');
    }
    return response.json();
  },
};
