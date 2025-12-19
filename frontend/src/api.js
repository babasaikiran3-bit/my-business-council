/**
 * API client for the Eternal Ops Control backend.
 *
 * Features:
 * - WorkOS authentication with automatic token refresh on 401 responses
 * - Connection error detection for backend unavailability
 * - Health check endpoint for proactive connectivity monitoring
 * - SSE streaming support with connection error handling
 *
 * Connection Error Flow:
 * 1. ApiConnectionHandler sets callback via setConnectionErrorCallback()
 * 2. API calls detect network failures via isConnectionError()
 * 3. reportConnectionError() invokes callback with error details
 * 4. ConnectionErrorContext updates state, triggering UI banner display
 */

// Use environment variable for API base URL, fallback to localhost for development
// In production (Vercel), the API is at the same origin under /api
const API_BASE = import.meta.env.VITE_API_BASE_URL || (
  import.meta.env.PROD ? '' : 'http://localhost:8001'
);

// Token getter function from WorkOS AuthKit's useAuth hook
let getAccessToken = null;

// Track if we're currently refreshing to prevent multiple refresh attempts
let isRefreshing = false;
let refreshPromise = null;

// Connection error callback - bridges API client to React context for UI display
let connectionErrorCallback = null;

/**
 * Check if an error indicates a connection/network problem.
 *
 * Distinguishes between:
 * - Connection errors (server down, network issues) → Show connection banner
 * - Auth errors (401, 403) → Handled by auth flow
 * - Validation errors (400, 422) → Show inline error messages
 *
 * @param {Error} error - The error to check
 * @returns {boolean} True if this is a connection error that should trigger the banner
 */
function isConnectionError(error) {
  // TypeError with 'fetch' - common when server is unreachable
  if (error instanceof TypeError && error.message.includes('fetch')) {
    return true;
  }

  // Explicit network error message
  if (error.message?.toLowerCase().includes('network')) {
    return true;
  }

  // "Failed to fetch" - browser's generic network failure message
  if (error.message?.toLowerCase().includes('failed to fetch')) {
    return true;
  }

  // Connection refused - server not running
  if (error.message?.toLowerCase().includes('connection refused')) {
    return true;
  }

  // CORS errors can indicate server is down (no response to preflight)
  if (error.message?.toLowerCase().includes('cors')) {
    return true;
  }

  // Chrome-style error codes (ERR_CONNECTION_REFUSED, etc.)
  if (error.message?.toLowerCase().includes('err_connection')) {
    return true;
  }

  // Safari's "Load failed" message for network errors
  if (error.message?.toLowerCase().includes('load failed')) {
    return true;
  }

  return false;
}

/**
 * Check if an HTTP status code indicates a server-side connection issue
 * @param {number} status - HTTP status code
 * @returns {boolean} True if this is a server error
 */
function isServerError(status) {
  return status >= 500 && status < 600;
}

/**
 * Report a connection error through the registered callback.
 *
 * This function bridges the API client to the React UI by invoking the callback
 * set by ApiConnectionHandler. The callback updates ConnectionErrorContext state,
 * which triggers the ConnectionErrorBanner to display.
 *
 * @param {string} type - Error type from CONNECTION_ERROR_TYPES (e.g., 'NETWORK_ERROR')
 * @param {string} message - User-friendly error message to display in the banner
 * @param {Function} retryFn - Optional async function to retry the failed operation
 */
function reportConnectionError(type, message, retryFn = null) {
  if (connectionErrorCallback) {
    connectionErrorCallback({ type, message, retryFn });
  }
}

export const api = {
  /**
   * Set the token getter function from WorkOS AuthKit's useAuth hook.
   * WorkOS AuthKit's getAccessToken supports a forceRefresh option.
   */
  setTokenGetter(tokenGetter) {
    getAccessToken = tokenGetter;
  },

  /**
   * Set the connection error callback for reporting backend unavailability.
   *
   * Called by ApiConnectionHandler on mount to connect the API client to the
   * ConnectionErrorContext. When connection errors occur, the callback is invoked
   * to update React state and display the error banner.
   *
   * @param {Function|null} callback - Function to call with { type, message, retryFn }
   */
  setConnectionErrorCallback(callback) {
    connectionErrorCallback = callback;
  },

  /**
   * Check if the backend server is available.
   *
   * This is a lightweight health check that:
   * - Runs immediately on app mount (triggered by ApiConnectionHandler)
   * - Does NOT require authentication (hits the root / endpoint)
   * - Uses AbortController for timeout (5 seconds) for browser compatibility
   *   (AbortSignal.timeout() is not supported in older browsers)
   * - Reports connection errors to trigger the UI banner
   *
   * @returns {Promise<boolean>} True if server is available, false otherwise
   */
  async checkHealth() {
    // AbortController with manual timeout for broader browser compatibility
    // (AbortSignal.timeout() is newer and less supported)
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    try {
      const response = await fetch(`${API_BASE}/`, {
        method: 'GET',
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      return response.ok;
    } catch (error) {
      clearTimeout(timeoutId);
      if (isConnectionError(error)) {
        const retryFn = () => this.checkHealth();
        reportConnectionError(
          'NETWORK_ERROR',
          'Dashboard has lost connection to the server. Please check that the backend is running.',
          retryFn
        );
      }
      return false;
    }
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
   * Make a fetch request with automatic 401 retry and connection error detection.
   * If a 401 is received, refreshes the token and retries once.
   * If a network/connection error occurs, reports it via the callback.
   */
  async fetchWithRetry(url, options = {}, retryCount = 0) {
    const authHeaders = await this.getAuthHeaders();

    let response;
    try {
      response = await fetch(url, {
        ...options,
        headers: {
          ...options.headers,
          ...authHeaders,
        },
      });
    } catch (error) {
      // Check if this is a connection/network error
      if (isConnectionError(error)) {
        console.error('Connection error detected:', error.message);
        // Create a retry function that will re-attempt this request
        const retryFn = () => this.fetchWithRetry(url, options, 0);
        reportConnectionError(
          'NETWORK_ERROR',
          'Dashboard has lost connection to the server. Please check that the backend is running.',
          retryFn
        );
      }
      throw error;
    }

    // Check for server errors (5xx) which may indicate server issues
    if (isServerError(response.status)) {
      console.error(`Server error: ${response.status}`);
      const retryFn = () => this.fetchWithRetry(url, options, 0);
      reportConnectionError(
        'SERVER_ERROR',
        `Server error (${response.status}). The server may be experiencing issues.`,
        retryFn
      );
      // Still return the response so the caller can handle it
      return response;
    }

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
   * Get a scoped Typesense search key for the authenticated user.
   * The key has user_id filtering embedded at the Typesense level.
   * @returns {Promise<{search_key: string, typesense_host: string, typesense_port: string, typesense_protocol: string}>}
   */
  async getSearchKey() {
    const response = await this.fetchWithRetry(`${API_BASE}/api/search/key`);
    if (!response.ok) {
      if (response.status === 401) {
        throw new Error('Authentication required. Please sign in again.');
      }
      if (response.status === 503) {
        throw new Error('Search is not configured.');
      }
      throw new Error('Failed to get search key');
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
   * @param {Object} options - Additional options
   * @param {string|null} options.originalQuery - Original query before improvement (if prompt was improved)
   * @param {AbortSignal|null} options.signal - AbortController signal for cancellation
   * @param {Object|null} options.completedStages - Previously completed stage data for smart retry
   * @param {Array|null} options.completedStages.stage1 - Stage 1 responses to reuse
   * @param {Array|null} options.completedStages.stage2 - Stage 2 rankings to reuse
   * @param {Object|null} options.completedStages.stage2Metadata - Stage 2 metadata (label_to_model, aggregate_rankings)
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent, options = {}) {
    const { originalQuery = null, signal = null, completedStages = null } = options;
    const authHeaders = await this.getAuthHeaders();
    const body = { content };
    if (originalQuery) {
      body.original_query = originalQuery;
    }
    // Smart retry: include previously completed stage data to skip re-running them
    if (completedStages) {
      if (completedStages.stage1) {
        body.stage1_data = completedStages.stage1;
      }
      if (completedStages.stage2) {
        body.stage2_data = completedStages.stage2;
      }
      if (completedStages.stage2Metadata) {
        body.stage2_metadata = completedStages.stage2Metadata;
      }
    }

    const fetchOptions = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders,
      },
      body: JSON.stringify(body),
    };

    // Add abort signal if provided
    if (signal) {
      fetchOptions.signal = signal;
    }

    let response;
    try {
      response = await fetch(
        `${API_BASE}/api/conversations/${conversationId}/message/stream`,
        fetchOptions
      );
    } catch (error) {
      // Check if this is a connection/network error (not an abort)
      if (error.name !== 'AbortError' && isConnectionError(error)) {
        console.error('SSE connection error detected:', error.message);
        reportConnectionError(
          'NETWORK_ERROR',
          'Dashboard has lost connection to the server. Please check that the backend is running.',
          null
        );
      }
      throw error;
    }

    // Handle 401 with token refresh for SSE
    if (response.status === 401) {
      console.log('SSE received 401, attempting token refresh and retry...');
      const newHeaders = await this.refreshToken();
      const retryOptions = {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...newHeaders,
        },
        body: JSON.stringify(body),
      };
      if (signal) {
        retryOptions.signal = signal;
      }
      try {
        response = await fetch(
          `${API_BASE}/api/conversations/${conversationId}/message/stream`,
          retryOptions
        );
      } catch (error) {
        if (error.name !== 'AbortError' && isConnectionError(error)) {
          console.error('SSE retry connection error:', error.message);
          reportConnectionError(
            'NETWORK_ERROR',
            'Dashboard has lost connection to the server. Please check that the backend is running.',
            null
          );
        }
        throw error;
      }
    }

    // Check for server errors
    if (isServerError(response.status)) {
      console.error(`SSE server error: ${response.status}`);
      reportConnectionError(
        'SERVER_ERROR',
        `Server error (${response.status}). The server may be experiencing issues.`,
        null
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

    try {
      while (true) {
        // Check if aborted before reading
        if (signal?.aborted) {
          reader.cancel();
          throw new DOMException('Stream aborted', 'AbortError');
        }

        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        console.log('[SSE] Received chunk:', chunk.substring(0, 200) + (chunk.length > 200 ? '...' : ''));
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            try {
              const event = JSON.parse(data);
              console.log('[SSE] Parsed event:', event.type, event);
              onEvent(event.type, event);
            } catch (e) {
              console.error('[SSE] Failed to parse SSE event:', e, 'data:', data.substring(0, 100));
            }
          }
        }
      }
    } catch (error) {
      // Re-throw AbortError for proper handling upstream
      if (error.name === 'AbortError') {
        throw error;
      }
      // For other errors, try to cancel the reader and re-throw
      try {
        reader.cancel();
      } catch {
        // Ignore cancel errors
      }
      throw error;
    }
  },
};
