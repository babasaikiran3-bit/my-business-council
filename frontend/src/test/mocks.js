/**
 * Mock implementations for testing CopilotFeature
 */
import { vi } from 'vitest'

/**
 * Creates a mock API object for testing
 * @returns {Object} Mock API with all necessary methods
 */
export function createMockApi() {
  return {
    listConversations: vi.fn().mockResolvedValue([]),
    getConversation: vi.fn().mockResolvedValue({
      id: 'conv-1',
      title: 'Test Conversation',
      messages: [],
    }),
    createConversation: vi.fn().mockResolvedValue({
      id: 'new-conv',
      title: 'New Conversation',
      created_at: new Date().toISOString(),
    }),
    sendMessageStream: vi.fn().mockImplementation(async (convId, content, onEvent, options) => {
      // Default implementation: simulate successful stream
      onEvent('stage1_start', { models: ['model-1', 'model-2'] })
      onEvent('model_response', { model: 'model-1', success: true, elapsed_ms: 1000 })
      onEvent('model_response', { model: 'model-2', success: true, elapsed_ms: 1500 })
      onEvent('stage1_complete', { data: [{ model: 'model-1', content: 'Response 1' }] })
      onEvent('stage2_start', {})
      onEvent('stage2_complete', { data: [], metadata: { aggregate_rankings: [] } })
      onEvent('stage3_start', {})
      onEvent('stage3_complete', { data: 'Final answer' })
      onEvent('title_complete', {})
      onEvent('complete', {})
    }),
    improvePrompt: vi.fn().mockResolvedValue({
      improved_prompt: 'Improved prompt text',
    }),
  }
}

/**
 * Creates a mock toast object for testing
 * @returns {Object} Mock toast with all necessary methods
 */
export function createMockToast() {
  return {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }
}

/**
 * Creates a mock AuthKit context for testing
 * @returns {Object} Mock auth context
 */
export function createMockAuthContext() {
  return {
    user: {
      id: 'test-user-id',
      email: 'test@eternal.ag',
      firstName: 'Test',
      lastName: 'User',
    },
    isLoading: false,
    getAccessToken: vi.fn().mockResolvedValue('mock-access-token'),
    signIn: vi.fn(),
    signOut: vi.fn(),
  }
}

/**
 * Creates a mock navigate function for testing
 * @returns {Function} Mock navigate function
 */
export function createMockNavigate() {
  return vi.fn()
}

