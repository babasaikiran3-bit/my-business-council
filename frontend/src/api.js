/**
 * API client for the Eternal Copilot backend with WorkOS authentication.
 * Includes automatic token refresh and retry on 401 responses.
 */

// Use environment variable for API base URL, fallback to localhost for development
// In production (Vercel), the API is at the same origin under /api
const API_BASE = import.meta.env.VITE_API_BASE_URL || (
  import.meta.env.PROD ? '' : 'http://localhost:8001'
);

let getAccessToken = null;

// Track if we're currently refreshing to prevent multiple refresh attempts
let isRefreshing = false;
let refreshPromise = null;

export const api = {
  /**
   * Set the token getter function from WorkOS AuthKit's useAuth hook.
   * WorkOS AuthKit's getAccessToken supports a forceRefresh option.
   */
  setTokenGetter(tokenGetter) {
    getAccessToken = tokenGetter;
  },

  /**
   * Get authorization headers with WorkOS access token.
   * @param {boolean} forceRefresh - Force token refresh before getting headers
   */
  async getAuthHeaders(forceRefresh = false) {
    if (!getAccessToken) return {};

    try {
      // WorkOS AuthKit's getAccessToken accepts options including forceRefresh
      const token = await getAccessToken({ forceRefresh });
      return token ? { 'Authorization': `Bearer ${token}` } : {};
    } catch (error) {
      console.error('Failed to get access token:', error);
      return {};
    }
  },

  /**
   * Force refresh the access token.
   * Returns new auth headers or throws if refresh fails.
   */
  async refreshToken() {
    // Prevent multiple simultaneous refresh attempts
    if (isRefreshing) {
      return refreshPromise;
    }

    isRefreshing = true;
    refreshPromise = this.getAuthHeaders(true);

    try {
      const headers = await refreshPromise;
      return headers;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  },

  /**
   * Make a fetch request with automatic 401 retry.
   * If a 401 is received, refreshes the token and retries once.
   */
  async fetchWithRetry(url, options = {}, retryCount = 0) {
    const authHeaders = await this.getAuthHeaders();
    const response = await fetch(url, {
      ...options,
      headers: {
        ...options.headers,
        ...authHeaders,
      },
    });

    // If 401 and haven't retried yet, refresh token and retry once
    if (response.status === 401 && retryCount < 1) {
      console.log('Received 401, attempting token refresh and retry...');

      try {
        const newHeaders = await this.refreshToken();

        // Retry the request with new token
        const retryResponse = await fetch(url, {
          ...options,
          headers: {
            ...options.headers,
            ...newHeaders,
          },
        });

        return retryResponse;
      } catch (refreshError) {
        console.error('Token refresh failed:', refreshError);
        // Return original 401 response if refresh fails
        return response;
      }
    }

    return response;
  },

  /**
   * List all conversations for the authenticated user.
   */
  async listConversations() {
    const response = await this.fetchWithRetry(`${API_BASE}/api/conversations`);
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please sign in again.');
      }
      throw new Error('Failed to list conversations');
    }
    return response.json();
  },

  /**
   * Create a new conversation.
   */
  async createConversation() {
    const response = await this.fetchWithRetry(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please sign in again.');
      }
      throw new Error('Failed to create conversation');
    }
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await this.fetchWithRetry(
      `${API_BASE}/api/conversations/${conversationId}`
    );
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please sign in again.');
      }
      throw new Error('Failed to get conversation');
    }
    return response.json();
  },

  /**
   * Improve a prompt using an LLM.
   */
  async improvePrompt(content) {
    const response = await this.fetchWithRetry(`${API_BASE}/api/improve-prompt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please sign in again.');
      }
      throw new Error('Failed to improve prompt');
    }
    return response.json();
  },

  /**
   * Send a message in a conversation.
   */
  async sendMessage(conversationId, content) {
    const response = await this.fetchWithRetry(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      }
    );
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please sign in again.');
      }
      throw new Error('Failed to send message');
    }
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * Note: SSE streams use initial token; if token expires mid-stream,
   * the stream will fail and should be retried by the caller.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent) {
    const authHeaders = await this.getAuthHeaders();
    let response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders,
        },
        body: JSON.stringify({ content }),
      }
    );

    // Handle 401 with token refresh for SSE
    if (response.status === 401) {
      console.log('SSE received 401, attempting token refresh and retry...');
      const newHeaders = await this.refreshToken();
      response = await fetch(
        `${API_BASE}/api/conversations/${conversationId}/message/stream`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...newHeaders,
          },
          body: JSON.stringify({ content }),
        }
      );
    }

    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please sign in again.');
      }
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
};
