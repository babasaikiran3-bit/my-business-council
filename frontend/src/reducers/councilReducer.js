/**
 * Pure reducer for council SSE progress events applied to the last assistant message.
 *
 * Each action mirrors an SSE event type from the backend stream.  The reducer
 * is a pure function: `(message, action) => nextMessage`.  It is intentionally
 * free of React imports so it can be tested in isolation.
 */

/**
 * Factory: returns a fresh assistant-message placeholder used before the first
 * SSE event arrives.  Always returns a new object to avoid accidental mutation.
 */
export function createAssistantMessage() {
  return {
    role: 'assistant',
    live: {},
    stage: null,
    stage1: null,
    stage2: null,
    stage3: null,
    metadata: null,
    research: null,
  };
}

/**
 * Reduce a single assistant message through one SSE action.
 *
 * @param {object}  message  - The current assistant message (mutated copy is fine).
 * @param {object}  action   - `{ type, ...payload }` matching an SSE event.
 * @returns {object} A new message object.
 */
export function councilReducer(message, action) {
  switch (action.type) {
    // ── progress / stage banner ──────────────────────────────────────
    case 'STAGE':
      return { ...message, stage: action.stage };

    // ── live agent status updates ────────────────────────────────────
    case 'AGENT':
      return {
        ...message,
        live: {
          ...message.live,
          [action.model]: {
            ...(message.live[action.model] || {}),
            status: action.status,
            reason: action.reason,
          },
        },
      };

    case 'TOOL':
      return {
        ...message,
        live: {
          ...message.live,
          [action.model]: {
            status: 'working',
            tool: action.tool,
            detail: action.detail,
          },
        },
      };

    case 'THOUGHT':
      return {
        ...message,
        live: {
          ...message.live,
          [action.model]: {
            status: 'working',
            thought: action.text,
          },
        },
      };

    // ── stage results ────────────────────────────────────────────────
    case 'RESULT':
      return {
        ...message,
        stage1: [
          ...(message.stage1 || []).filter((r) => r.model !== action.model),
          { model: action.model, response: action.text },
        ],
      };

    case 'RESEARCH':
      return {
        ...message,
        research: { model: action.model, brief: action.brief },
        live: {},
      };

    case 'RANKING':
      return {
        ...message,
        metadata: {
          ...(message.metadata || {}),
          aggregate_rankings: action.aggregate,
        },
      };

    case 'METADATA':
      return {
        ...message,
        metadata: { ...(message.metadata || {}), ...action.metadata },
      };

    case 'CONSENSUS_FILE':
      return { ...message, consensusFile: action.path };

    case 'FINAL':
      return {
        ...message,
        stage3: { model: action.model, response: action.text },
      };

    // ── terminal events ──────────────────────────────────────────────
    case 'DONE':
      return {
        ...message,
        stage1: action.stage1,
        stage2: action.stage2,
        stage3: action.stage3,
        metadata: action.metadata,
        research: action.metadata?.research ?? message.research,
        stage: null,
        live: {},
      };

    case 'FATAL':
      return { ...message, error: action.message, stage: null };

    // ── generic error (used outside SSE — e.g. consensus failures) ───
    case 'ERROR':
      return { ...message, error: action.message };

    default:
      return message;
  }
}
