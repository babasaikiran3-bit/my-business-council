import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import { toast } from 'sonner'
import { api } from '../../api'
import { isConnectionError } from '@/contexts/ConnectionErrorContext'
import ConversationSidebar from './copilot/ConversationSidebar'
import ChatInterface from '../ChatInterface'
import {
  useConversations,
  DEFAULT_STAGE_TIMINGS,
  STREAM_TIMEOUT_MS,
  MAX_SIMULTANEOUS_STREAMS,
  STALE_CHECK_INTERVAL_MS,
  STALE_THRESHOLD_MS,
  createInitialStreamState,
} from '@/hooks'

/**
 * CopilotFeature - The 3-stage LLM deliberation feature.
 * This wraps the existing Copilot functionality for use within the dashboard.
 *
 * ARCHITECTURE: Per-Conversation Stream Tracking
 * ================================================
 * This component supports multiple simultaneous conversations processing in parallel.
 * When a user switches away from a processing conversation, the stream continues in
 * the background and state is preserved. When they return, the UI reconnects to show
 * accumulated progress.
 *
 * Key data structures:
 * - conversationStreams: State object mapping conversation IDs to their stream state
 * - streamControllersRef: Ref holding Map of conversation ID → AbortController
 *
 * @param {Object} props
 * @param {string} props.initialConversationId - Optional conversation ID to load on mount (from search)
 */

// Valid in-progress status values (deliberation not yet complete or failed)
const IN_PROGRESS_STATUSES = [
  'pending',
  'stage1_in_progress',
  'stage1_complete',
  'stage2_in_progress',
  'stage2_complete',
  'stage3_in_progress',
]

/**
 * Check if a response_status indicates the deliberation is still in progress.
 * Defined outside component to ensure stable reference for useCallback dependencies.
 * @param {string} status - The response_status from the database
 * @returns {boolean} True if the deliberation is still being processed
 */
const isInProgressStatus = (status) => IN_PROGRESS_STATUSES.includes(status)

/**
 * Get the current stage name from a response_status for display.
 * Defined outside component to ensure stable reference.
 * @param {string} status - The response_status from the database
 * @returns {string} Human-readable stage description
 */
const getStageFromStatus = (status) => {
  switch (status) {
    case 'pending':
    case 'stage1_in_progress':
      return 'Stage 1: Collecting responses'
    case 'stage1_complete':
    case 'stage2_in_progress':
      return 'Stage 2: Peer rankings'
    case 'stage2_complete':
    case 'stage3_in_progress':
      return 'Stage 3: Synthesizing'
    default:
      return 'Processing'
  }
}

// Note: STALE_CHECK_INTERVAL_MS and STALE_THRESHOLD_MS are imported from @/hooks
// to ensure consistent timeout configuration across the codebase.

export default function CopilotFeature({ initialConversationId }) {
  // ============================================================================
  // CONVERSATION LIST STATE (with pagination) - extracted to useConversations hook
  // ============================================================================
  const {
    conversations,
    isLoadingConversations,
    isLoadingMore,
    hasMoreConversations,
    loadConversations,
    loadMoreConversations,
    addConversation,
    updateConversation: updateConversationInList,
  } = useConversations()

  // ============================================================================
  // CURRENT CONVERSATION STATE (what's visible in the UI)
  // ============================================================================
  const [currentConversationId, setCurrentConversationId] = useState(null)
  // Initialize with a draft conversation so users can start typing immediately
  // id: null indicates this is a draft, not yet persisted to backend
  const [currentConversation, setCurrentConversation] = useState({
    id: null,
    messages: [],
    title: null,
  })
  // Track when we're creating a conversation on first message send
  const [isCreatingConversation, setIsCreatingConversation] = useState(false)

  // ============================================================================
  // POLLING STATE FOR RECOVERY (when page refreshed during deliberation)
  // ============================================================================
  // Track conversations being polled for in-progress deliberations
  // Structure: { [conversationId]: { status: 'stage2_in_progress', responseId: '...' } }
  const [pollingConversations, setPollingConversations] = useState({})

  // Track which conversations have a cancel request in progress
  // Structure: { [conversationId]: true }
  const [cancellingConversations, setCancellingConversations] = useState({})

  // Track which response is being resumed
  // Structure: { responseId: true }
  const [resumingResponses, setResumingResponses] = useState({})

  // ============================================================================
  // PER-CONVERSATION STREAM TRACKING (supports multiple simultaneous streams)
  // ============================================================================
  /**
   * Stores streaming state for ALL active conversations, not just the current one.
   * Structure: { [conversationId]: StreamState }
   *
   * StreamState = {
   *   isLoading: boolean,
   *   stageTimings: { stage1: {...}, stage2: {...}, stage3: {...} },
   *   modelStatuses: { [modelName]: 'pending'|'processing'|'received'|'failed' },
   *   modelTimings: { [modelName]: elapsedMs },
   *   error: { message, content, originalQuery } | null,
   *   conversation: { id, messages, title } // Preserved during background processing
   * }
   */
  const [conversationStreams, setConversationStreams] = useState({})

  /**
   * AbortControllers for active streams.
   * Map: conversationId → AbortController
   * Stored in ref (not state) because AbortController is mutable and we don't
   * want its mutations to trigger re-renders.
   */
  const streamControllersRef = useRef(new Map())

  /**
   * Timeout IDs for active streams.
   * Map: conversationId → timeoutId
   * Timeouts auto-abort streams that receive no events within STREAM_TIMEOUT_MS.
   */
  const streamTimeoutsRef = useRef(new Map())

  // Track mounted state for safe async updates
  const isMountedRef = useRef(true)

  /**
   * Ref to track the actual current conversation ID at any moment.
   * This is used in event handlers to correctly determine if a stream event
   * occurred in the background (user switched away from that conversation).
   * Using a ref avoids stale closure issues when rapidly switching conversations.
   */
  const currentConversationIdRef = useRef(currentConversationId)

  // ============================================================================
  // DERIVED STATE FROM CURRENT CONVERSATION'S STREAM
  // ============================================================================
  /**
   * Get the current conversation's stream state (if any).
   * This drives all the UI indicators for the currently visible conversation.
   */
  const currentStreamState = useMemo(() => {
    return currentConversationId ? conversationStreams[currentConversationId] : null
  }, [currentConversationId, conversationStreams])

  // Derived values for UI - falls back to defaults when no active stream
  const isLoading = currentStreamState?.isLoading || false
  const stageTimings = currentStreamState?.stageTimings || DEFAULT_STAGE_TIMINGS
  const modelStatuses = currentStreamState?.modelStatuses || {}
  const modelTimings = currentStreamState?.modelTimings || {}
  const currentError = currentStreamState?.error || null

  // CRITICAL: When an active stream exists, use its conversation directly to keep
  // stageTimings and msg.loading in sync. This prevents race conditions where
  // stageTimings.stage3 updates but msg.loading.stage3 hasn't propagated yet
  // (due to the useEffect sync delay for currentConversation state).
  const activeConversation = currentStreamState?.conversation || currentConversation

  // ============================================================================
  // STREAM STATE MANAGEMENT HELPERS
  // ============================================================================

  /**
   * Update the stream state for a specific conversation.
   * This is the primary way to modify conversationStreams.
   * @param {string} conversationId - The conversation to update
   * @param {function|object} updater - Either an updater function or partial state object
   */
  const updateStreamState = useCallback((conversationId, updater) => {
    setConversationStreams(prev => {
      const currentState = prev[conversationId]
      if (!currentState) return prev // No stream state for this conversation

      const updates = typeof updater === 'function' ? updater(currentState) : updater
      return {
        ...prev,
        [conversationId]: { ...currentState, ...updates }
      }
    })
  }, [])

  /**
   * Update nested conversation data within a stream state.
   * Used when stream events modify the in-progress conversation.
   * @param {string} conversationId - The conversation to update
   * @param {function} conversationUpdater - Updater function receiving current conversation
   */
  const updateStreamConversation = useCallback((conversationId, conversationUpdater) => {
    setConversationStreams(prev => {
      const currentState = prev[conversationId]
      if (!currentState?.conversation) return prev

      return {
        ...prev,
        [conversationId]: {
          ...currentState,
          conversation: conversationUpdater(currentState.conversation)
        }
      }
    })
  }, [])

  /**
   * Mark a stage as completed for a specific conversation.
   * Calculates and stores the final elapsed time to stop the timer display.
   * @param {string} conversationId - The conversation ID
   * @param {string} stageName - 'stage1', 'stage2', or 'stage3'
   */
  const markStageCompleted = useCallback((conversationId, stageName) => {
    updateStreamState(conversationId, prev => {
      const stageTiming = prev.stageTimings[stageName]
      const finalElapsed = stageTiming.startTime
        ? Date.now() - stageTiming.startTime
        : 0
      return {
        stageTimings: {
          ...prev.stageTimings,
          [stageName]: {
            ...stageTiming,
            completed: true,
            elapsed: finalElapsed  // Store final elapsed time to stop the timer
          }
        }
      }
    })
  }, [updateStreamState])

  /**
   * Clear the timeout for a stream (call when events are received or stream ends).
   * @param {string} conversationId - The conversation ID
   */
  const clearStreamTimeout = useCallback((conversationId) => {
    const timeoutId = streamTimeoutsRef.current.get(conversationId)
    if (timeoutId) {
      clearTimeout(timeoutId)
      streamTimeoutsRef.current.delete(conversationId)
    }
  }, [])

  /**
   * Clean up a completed or failed stream.
   * Removes the stream state, AbortController, and timeout.
   * @param {string} conversationId - The conversation to clean up
   */
  const cleanupStream = useCallback((conversationId) => {
    // Remove from conversationStreams
    setConversationStreams(prev => {
      const { [conversationId]: removed, ...rest } = prev
      return rest
    })
    // Remove AbortController
    streamControllersRef.current.delete(conversationId)
    // Clear timeout
    clearStreamTimeout(conversationId)
  }, [clearStreamTimeout])

  /**
   * Abort and clean up a stream for a conversation.
   * @param {string} conversationId - The conversation to abort
   */
  const abortStream = useCallback((conversationId) => {
    const controller = streamControllersRef.current.get(conversationId)
    if (controller) {
      controller.abort()
    }
    cleanupStream(conversationId)
  }, [cleanupStream])

  // ============================================================================
  // LIFECYCLE EFFECTS
  // ============================================================================

  // Cleanup ALL streams on unmount
  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      // Abort all active streams
      streamControllersRef.current.forEach((controller) => {
        controller.abort()
      })
      streamControllersRef.current.clear()
      // Clear all stream timeouts
      streamTimeoutsRef.current.forEach((timeoutId) => {
        clearTimeout(timeoutId)
      })
      streamTimeoutsRef.current.clear()
    }
  }, [])

  // Load conversations on mount
  useEffect(() => {
    loadConversations()
  }, [])

  // Handle initial conversation ID from search navigation
  useEffect(() => {
    if (initialConversationId) {
      setCurrentConversationId(initialConversationId)
    }
  }, [initialConversationId])

  // Keep currentConversationIdRef in sync with state
  // This ensures event handlers always have the current value
  useEffect(() => {
    currentConversationIdRef.current = currentConversationId
  }, [currentConversationId])

  /**
   * Load conversation details when selected.
   * IMPORTANT: Skip loading if an active stream exists for this conversation,
   * because we want to preserve the in-progress streaming data.
   */
  useEffect(() => {
    if (!currentConversationId) return

    // Check if this conversation has an active stream
    const hasActiveStream = streamControllersRef.current.has(currentConversationId)

    if (hasActiveStream) {
      // Conversation has active stream - restore from stream state instead of loading from API
      const streamState = conversationStreams[currentConversationId]
      if (streamState?.conversation) {
        setCurrentConversation(streamState.conversation)
      }
    } else {
      // No active stream - load from API
      loadConversation(currentConversationId)
    }
  }, [currentConversationId]) // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Sync currentConversation with stream state when stream updates the conversation.
   * This ensures the UI shows real-time updates when viewing an active stream.
   */
  useEffect(() => {
    if (currentConversationId && currentStreamState?.conversation) {
      setCurrentConversation(currentStreamState.conversation)
    }
  }, [currentConversationId, currentStreamState?.conversation])

  /**
   * Periodic cleanup effect for stale streams.
   * Detects and cleans up streams that have been in "loading" state for too long
   * without receiving any events. This is a safety net in case the timeout mechanism
   * in handleSendMessage fails (e.g., due to race conditions).
   */
  useEffect(() => {
    const cleanupInterval = setInterval(() => {
      const now = Date.now()

      setConversationStreams(prev => {
        const updated = { ...prev }
        let hasChanges = false

        for (const [convId, streamState] of Object.entries(prev)) {
          // Only check streams that are still loading
          if (!streamState.isLoading) continue

          const timeSinceLastEvent = now - (streamState.lastEventTime || 0)
          if (timeSinceLastEvent > STALE_THRESHOLD_MS) {
            console.warn(`Cleaning up stale stream: ${convId} (no events for ${Math.round(timeSinceLastEvent / 1000)}s)`)

            // Mark as error instead of just removing (preserves user's message for retry)
            updated[convId] = {
              ...streamState,
              isLoading: false,
              error: {
                message: 'The deliberation appears to have stalled. Please try again.',
                content: '', // We don't have access to original content here
                originalQuery: null,
              },
            }

            // Abort the stream
            const controller = streamControllersRef.current.get(convId)
            if (controller) {
              controller.abort()
            }
            streamControllersRef.current.delete(convId)

            // Clear timeout
            const timeoutId = streamTimeoutsRef.current.get(convId)
            if (timeoutId) {
              clearTimeout(timeoutId)
              streamTimeoutsRef.current.delete(convId)
            }

            hasChanges = true
          }
        }

        return hasChanges ? updated : prev
      })
    }, STALE_CHECK_INTERVAL_MS)

    return () => clearInterval(cleanupInterval)
  }, [])

  // Ref to track active polling intervals (conversationId -> intervalId)
  const pollingIntervalsRef = useRef(new Map())

  /**
   * Stop polling for a specific conversation.
   */
  const stopPolling = useCallback((conversationId) => {
    const intervalId = pollingIntervalsRef.current.get(conversationId)
    if (intervalId) {
      clearInterval(intervalId)
      pollingIntervalsRef.current.delete(conversationId)
      console.log(`[Polling] Stopped polling for conversation ${conversationId}`)
    }
    // Remove from polling state
    setPollingConversations(prev => {
      const { [conversationId]: removed, ...rest } = prev
      return rest
    })
  }, [])

  /**
   * Cancel a stale/orphaned deliberation.
   * This marks the response as 'failed' in the database so the user can retry.
   * @param {string} conversationId - The conversation ID
   * @param {string} responseId - The response ID to cancel
   */
  const handleCancelDeliberation = useCallback(async (conversationId, responseId) => {
    if (!responseId) {
      console.error('[Cancel] No responseId provided')
      toast.error('Cannot cancel: missing response ID')
      return
    }

    console.log(`[Cancel] Cancelling deliberation for conversation ${conversationId}, responseId=${responseId}`)

    // Mark as cancelling for UI feedback
    setCancellingConversations(prev => ({ ...prev, [conversationId]: true }))

    try {
      const result = await api.cancelResponse(responseId)
      console.log(`[Cancel] Successfully cancelled: ${result.message}`)

      // Stop polling since the deliberation is now marked as failed
      stopPolling(conversationId)

      // Reload the conversation to get the updated state
      const conv = await api.getConversation(conversationId)
      setCurrentConversation(conv)

      toast.success('Deliberation cancelled', {
        description: 'You can now retry by sending a new message.',
      })
    } catch (error) {
      console.error('[Cancel] Failed to cancel deliberation:', error)
      if (!isConnectionError(error)) {
        toast.error('Failed to cancel deliberation', {
          description: error.message || 'Please try again.',
        })
      }
    } finally {
      // Clear cancelling state
      setCancellingConversations(prev => {
        const { [conversationId]: removed, ...rest } = prev
        return rest
      })
    }
  }, [stopPolling])

  /**
   * Resume a failed deliberation from the last completed stage.
   * Uses the backend resume endpoint which reuses persisted stage data.
   * @param {string} responseId - The response ID to resume
   */
  const handleResumeDeliberation = useCallback(async (responseId) => {
    if (!responseId) {
      console.error('[Resume] No responseId provided')
      toast.error('Cannot resume: missing response ID')
      return
    }

    // Get current conversation ID for stream state management
    const conversationId = currentConversationId
    if (!conversationId) {
      console.error('[Resume] No current conversation')
      toast.error('Cannot resume: no conversation selected')
      return
    }

    console.log(`[Resume] Resuming deliberation for responseId=${responseId}, conversationId=${conversationId}`)

    // Mark as resuming for UI feedback
    setResumingResponses(prev => ({ ...prev, [responseId]: true }))

    // Initialize stream state for the resume (enables timers)
    // IMPORTANT: Include lastEventTime to prevent stale stream detector from immediately marking as stalled
    setConversationStreams(prev => ({
      ...prev,
      [conversationId]: {
        isLoading: true,
        stageTimings: { ...DEFAULT_STAGE_TIMINGS },
        modelStatuses: {},
        modelTimings: {},
        partialStage1Responses: [],
        error: null,
        conversation: currentConversation,
        lastEventTime: Date.now(),  // Critical: prevents false "stalled" errors
      }
    }))

    try {
      // Create an AbortController for this stream
      const controller = new AbortController()

      // Update the last assistant message to show loading state
      setCurrentConversation(prev => {
        if (!prev?.messages?.length) return prev
        const messages = [...prev.messages]
        const lastMsg = messages[messages.length - 1]
        if (lastMsg?.role === 'assistant' && lastMsg.response_id === responseId) {
          messages[messages.length - 1] = {
            ...lastMsg,
            response_status: 'resuming',
            loading: { stage1: false, stage2: false, stage3: false },
          }
        }
        return { ...prev, messages }
      })

      // Stream the resume response
      await api.resumeDeliberation(responseId, (eventType, event) => {
        console.log(`[Resume] Event: ${eventType}`, event)

        // Update lastEventTime for stale stream detection (prevents false "stalled" errors)
        updateStreamState(conversationId, { lastEventTime: Date.now() })

        // Handle resume-specific events
        if (eventType === 'resume_start') {
          toast.info(`Resuming from Stage ${event.resume_from_stage}`, {
            description: 'Reusing previously completed stage data...',
            duration: 3000,
          })
        }

        // Handle stage skip events (reused data) - mark as already completed
        if (eventType === 'stage1_skipped') {
          updateStreamState(conversationId, prev => ({
            stageTimings: {
              ...prev.stageTimings,
              stage1: { startTime: null, elapsed: 0, completed: true },
            },
          }))
          setCurrentConversation(prev => {
            if (!prev?.messages?.length) return prev
            const messages = [...prev.messages]
            const lastMsg = messages[messages.length - 1]
            if (lastMsg?.role === 'assistant' && lastMsg.response_id === responseId) {
              messages[messages.length - 1] = {
                ...lastMsg,
                stage1: event.data,
                loading: { ...lastMsg.loading, stage1: false },
              }
            }
            return { ...prev, messages }
          })
        }

        if (eventType === 'stage2_skipped') {
          updateStreamState(conversationId, prev => ({
            stageTimings: {
              ...prev.stageTimings,
              stage2: { startTime: null, elapsed: 0, completed: true },
            },
          }))
          setCurrentConversation(prev => {
            if (!prev?.messages?.length) return prev
            const messages = [...prev.messages]
            const lastMsg = messages[messages.length - 1]
            if (lastMsg?.role === 'assistant' && lastMsg.response_id === responseId) {
              messages[messages.length - 1] = {
                ...lastMsg,
                stage2: event.data,
                metadata: event.metadata,
                loading: { ...lastMsg.loading, stage2: false },
              }
            }
            return { ...prev, messages }
          })
        }

        // Handle stage start events - update stageTimings to start timer
        if (eventType === 'stage1_start') {
          updateStreamState(conversationId, prev => ({
            stageTimings: {
              ...prev.stageTimings,
              stage1: { startTime: Date.now(), elapsed: 0, completed: false },
            },
          }))
          setCurrentConversation(prev => {
            if (!prev?.messages?.length) return prev
            const messages = [...prev.messages]
            const lastMsg = messages[messages.length - 1]
            if (lastMsg?.role === 'assistant' && lastMsg.response_id === responseId) {
              messages[messages.length - 1] = {
                ...lastMsg,
                loading: { ...lastMsg.loading, stage1: true },
              }
            }
            return { ...prev, messages }
          })
        }

        if (eventType === 'stage2_start') {
          updateStreamState(conversationId, prev => ({
            stageTimings: {
              ...prev.stageTimings,
              stage2: { startTime: Date.now(), elapsed: 0, completed: false },
            },
          }))
          setCurrentConversation(prev => {
            if (!prev?.messages?.length) return prev
            const messages = [...prev.messages]
            const lastMsg = messages[messages.length - 1]
            if (lastMsg?.role === 'assistant' && lastMsg.response_id === responseId) {
              messages[messages.length - 1] = {
                ...lastMsg,
                loading: { ...lastMsg.loading, stage1: false, stage2: true },
              }
            }
            return { ...prev, messages }
          })
        }

        if (eventType === 'stage3_start') {
          updateStreamState(conversationId, prev => ({
            stageTimings: {
              ...prev.stageTimings,
              stage3: { startTime: Date.now(), elapsed: 0, completed: false },
            },
          }))
          setCurrentConversation(prev => {
            if (!prev?.messages?.length) return prev
            const messages = [...prev.messages]
            const lastMsg = messages[messages.length - 1]
            if (lastMsg?.role === 'assistant' && lastMsg.response_id === responseId) {
              messages[messages.length - 1] = {
                ...lastMsg,
                loading: { ...lastMsg.loading, stage2: false, stage3: true },
              }
            }
            return { ...prev, messages }
          })
        }

        // Handle stage complete events - mark stage as completed to stop timer
        if (eventType === 'stage1_complete') {
          markStageCompleted(conversationId, 'stage1')
          setCurrentConversation(prev => {
            if (!prev?.messages?.length) return prev
            const messages = [...prev.messages]
            const lastMsg = messages[messages.length - 1]
            if (lastMsg?.role === 'assistant' && lastMsg.response_id === responseId) {
              messages[messages.length - 1] = {
                ...lastMsg,
                stage1: event.data,
                loading: { ...lastMsg.loading, stage1: false },
              }
            }
            return { ...prev, messages }
          })
        }

        if (eventType === 'stage2_complete') {
          markStageCompleted(conversationId, 'stage2')
          setCurrentConversation(prev => {
            if (!prev?.messages?.length) return prev
            const messages = [...prev.messages]
            const lastMsg = messages[messages.length - 1]
            if (lastMsg?.role === 'assistant' && lastMsg.response_id === responseId) {
              messages[messages.length - 1] = {
                ...lastMsg,
                stage2: event.data,
                metadata: event.metadata,
                loading: { ...lastMsg.loading, stage2: false },
              }
            }
            return { ...prev, messages }
          })
        }

        if (eventType === 'stage3_complete') {
          markStageCompleted(conversationId, 'stage3')
          setCurrentConversation(prev => {
            if (!prev?.messages?.length) return prev
            const messages = [...prev.messages]
            const lastMsg = messages[messages.length - 1]
            if (lastMsg?.role === 'assistant' && lastMsg.response_id === responseId) {
              messages[messages.length - 1] = {
                ...lastMsg,
                stage3: event.data,
                loading: { stage1: false, stage2: false, stage3: false },
              }
            }
            return { ...prev, messages }
          })
        }

        // Handle completion - clear stream state
        if (eventType === 'complete') {
          // Clear stream state since deliberation is complete
          setConversationStreams(prev => {
            const { [conversationId]: removed, ...rest } = prev
            return rest
          })
          setCurrentConversation(prev => {
            if (!prev?.messages?.length) return prev
            const messages = [...prev.messages]
            const lastMsg = messages[messages.length - 1]
            if (lastMsg?.role === 'assistant' && lastMsg.response_id === responseId) {
              messages[messages.length - 1] = {
                ...lastMsg,
                response_status: 'complete',
                loading: { stage1: false, stage2: false, stage3: false },
              }
            }
            return { ...prev, messages }
          })
          // Refresh conversation list to update the status in sidebar
          loadConversations()
          toast.success('Deliberation resumed successfully', {
            description: event.resumed ? 'Completed using previously saved stage data.' : 'Deliberation completed.',
          })
        }

        // Handle errors - clear stream state
        if (eventType === 'error') {
          // Clear stream state on error
          setConversationStreams(prev => {
            const { [conversationId]: removed, ...rest } = prev
            return rest
          })
          setCurrentConversation(prev => {
            if (!prev?.messages?.length) return prev
            const messages = [...prev.messages]
            const lastMsg = messages[messages.length - 1]
            if (lastMsg?.role === 'assistant' && lastMsg.response_id === responseId) {
              messages[messages.length - 1] = {
                ...lastMsg,
                response_status: 'failed',
                loading: { stage1: false, stage2: false, stage3: false },
              }
            }
            return { ...prev, messages }
          })
          toast.error('Resume failed', {
            description: event.message || 'An error occurred while resuming.',
          })
        }
      }, { signal: controller.signal })

    } catch (error) {
      console.error('[Resume] Error:', error)
      // Clear stream state on error
      setConversationStreams(prev => {
        const { [conversationId]: removed, ...rest } = prev
        return rest
      })
      if (!isConnectionError(error)) {
        toast.error('Failed to resume deliberation', {
          description: error.message || 'Please try again.',
        })
      }
      // Revert the loading state
      setCurrentConversation(prev => {
        if (!prev?.messages?.length) return prev
        const messages = [...prev.messages]
        const lastMsg = messages[messages.length - 1]
        if (lastMsg?.role === 'assistant' && lastMsg.response_id === responseId) {
          messages[messages.length - 1] = {
            ...lastMsg,
            response_status: 'failed',
            loading: { stage1: false, stage2: false, stage3: false },
          }
        }
        return { ...prev, messages }
      })
    } finally {
      // Clear resuming state
      setResumingResponses(prev => {
        const { [responseId]: removed, ...rest } = prev
        return rest
      })
    }
  }, [currentConversationId, currentConversation, updateStreamState, markStageCompleted, loadConversations])

  /**
   * Start polling for updates on an in-progress conversation.
   * @param {string} conversationId - The conversation ID to poll
   * @param {string} initialStatus - The initial response_status for UI display
   * @param {string} responseId - The response ID (needed for cancel functionality)
   */
  const startPolling = useCallback((conversationId, initialStatus, responseId = null) => {
    // Don't start if already polling
    if (pollingIntervalsRef.current.has(conversationId)) return

    console.log(`[Polling] Starting polling for conversation ${conversationId}, responseId=${responseId}`)

    // Add to polling state for UI indicator (include responseId for cancel functionality)
    setPollingConversations(prev => ({
      ...prev,
      [conversationId]: { status: initialStatus, responseId }
    }))

    const pollInterval = setInterval(async () => {
      try {
        const conv = await api.getConversation(conversationId)

        // Update the conversation in state
        setCurrentConversation(prev => {
          // Only update if we're still viewing this conversation
          if (prev?.id === conversationId) {
            return conv
          }
          return prev
        })

        // Check if the last assistant message is still in progress
        const lastMessage = conv.messages?.[conv.messages.length - 1]
        if (lastMessage?.role === 'assistant') {
          const status = lastMessage.response_status

          if (!isInProgressStatus(status)) {
            // Deliberation completed or failed - stop polling FIRST to prevent
            // any race condition where the UI briefly shows polling state alongside
            // completed Stage 3 content (Issue 5 fix)
            console.log(`[Polling] Conversation ${conversationId} finished with status: ${status}`)
            stopPolling(conversationId)

            if (status === 'complete') {
              toast.success('Deliberation completed', {
                description: 'The conversation has been updated with the final results.',
              })
            } else if (status === 'failed') {
              // Note: No isConnectionError() check needed here because the 'failed'
              // status comes from the database, meaning the backend successfully
              // stored the error state - this is not a connection failure.
              toast.error('Deliberation failed', {
                description: 'The processing encountered an error.',
              })
            }
          } else {
            // Still in progress - update polling state with current status and responseId
            const responseId = lastMessage.response_id
            setPollingConversations(prev => ({
              ...prev,
              [conversationId]: { status, responseId }
            }))
          }
        }
      } catch (error) {
        console.error(`[Polling] Error polling conversation ${conversationId}:`, error)
        // Stop polling on error to prevent infinite retries
        stopPolling(conversationId)

        // Show error toast only for non-connection errors (Issue 6 fix)
        // Connection errors are already handled by ConnectionErrorBanner
        if (!isConnectionError(error)) {
          toast.error('Failed to check deliberation status', {
            description: 'Polling stopped. Refresh the page to check for updates.',
          })
        }
      }
    }, 3000) // Poll every 3 seconds

    pollingIntervalsRef.current.set(conversationId, pollInterval)
  }, [stopPolling])

  // Cleanup all polling on unmount
  useEffect(() => {
    return () => {
      pollingIntervalsRef.current.forEach((intervalId, conversationId) => {
        clearInterval(intervalId)
      })
      pollingIntervalsRef.current.clear()
    }
  }, [])

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id)
      setCurrentConversation(conv)

      // Check if the last assistant message has an in-progress deliberation
      const lastMessage = conv.messages?.[conv.messages.length - 1]
      if (lastMessage?.role === 'assistant' && isInProgressStatus(lastMessage.response_status)) {
        const status = lastMessage.response_status
        const responseId = lastMessage.response_id
        console.log(`[Recovery] Detected in-progress deliberation: ${status}, responseId=${responseId}`)

        // Start polling for updates (pass status and responseId for UI indicator and cancel)
        startPolling(id, status, responseId)

        // Show a toast to inform the user
        toast.info('Deliberation in progress', {
          description: `${getStageFromStatus(status)} is still running. Updates will appear automatically.`,
          duration: 5000,
        })
      }
    } catch (error) {
      console.error('Failed to load conversation:', error)
      // Skip toast for connection errors - the ConnectionErrorBanner handles those
      if (!isConnectionError(error)) {
        toast.error('Failed to load conversation')
      }
    }
  }

  // ============================================================================
  // UI EVENT HANDLERS
  // ============================================================================

  const handleNewConversation = () => {
    // NOTE: We do NOT abort the current conversation's stream - it continues in background!
    // However, we DO stop polling since polling is only for the currently viewed conversation.
    if (currentConversationId && pollingIntervalsRef.current.has(currentConversationId)) {
      stopPolling(currentConversationId)
    }

    // Switch to a new draft conversation
    setCurrentConversationId(null)
    setCurrentConversation({
      id: null,
      messages: [],
      title: null,
    })
  }

  /**
   * Handle conversation selection from sidebar.
   * CRITICAL: We do NOT abort streams when switching - they continue in background.
   * The UI will sync to the target conversation's stream state (if any) via effects.
   *
   * However, we DO stop polling for the previous conversation since polling is only
   * relevant for the currently viewed conversation (unlike streams which run in background).
   */
  const handleSelectConversation = (id) => {
    if (id === currentConversationId) return // Already viewing this conversation

    // Stop polling for the previous conversation (if any) to prevent unnecessary API calls
    if (currentConversationId && pollingIntervalsRef.current.has(currentConversationId)) {
      stopPolling(currentConversationId)
    }

    setCurrentConversationId(id)
  }

  /**
   * Clear error for the current conversation's stream.
   * Removes the ENTIRE stream state to prevent memory leaks from accumulated
   * errored streams. The conversation data will be reloaded from API if needed.
   */
  const handleClearError = useCallback(() => {
    if (currentConversationId) {
      // Remove the entire stream state, not just the error field
      // This prevents indefinite accumulation of errored streams
      setConversationStreams(prev => {
        const { [currentConversationId]: removed, ...rest } = prev
        return rest
      })
      // Also ensure no controller remains
      streamControllersRef.current.delete(currentConversationId)
    }
  }, [currentConversationId])

  /**
   * Retry a failed message for the current conversation.
   *
   * SMART RETRY: Preserves and reuses any completed stage outputs from the failed attempt.
   * For example, if Stage 1 completed but Stage 2 failed, the retry will skip Stage 1
   * and reuse the collected responses, saving time and API calls.
   *
   * IMPORTANT: We remove the entire stream state before retrying, not just clear the error.
   * This ensures that stale stageTimings from the failed attempt don't briefly render
   * (e.g., showing Stage 3 progress when Stage 2 failed).
   */
  const handleRetryMessage = () => {
    if (!currentError) return
    const { content, originalQuery, completedStages } = currentError

    // Log what stages we're reusing for debugging
    if (completedStages?.stage1) {
      console.log('[SmartRetry] Reusing Stage 1 responses:', completedStages.stage1.length, 'responses')
    }
    if (completedStages?.stage2) {
      console.log('[SmartRetry] Reusing Stage 2 rankings')
    }

    // Remove the entire stream state (not just clear error) to prevent stale stageTimings
    // from briefly rendering during the retry. handleSendMessage will create fresh state.
    if (currentConversationId) {
      setConversationStreams(prev => {
        const { [currentConversationId]: removed, ...rest } = prev
        return rest
      })
      // Also ensure no controller remains
      streamControllersRef.current.delete(currentConversationId)
    }

    // Pass completed stages to handleSendMessage for smart retry
    handleSendMessage(content, originalQuery, completedStages)
  }

  /**
   * Cancel the stream for the currently visible conversation.
   */
  const handleCancelStream = useCallback(() => {
    if (currentConversationId && streamControllersRef.current.has(currentConversationId)) {
      abortStream(currentConversationId)
      toast.info('Deliberation cancelled')
    }
  }, [currentConversationId, abortStream])

  /**
   * Send a message and start streaming the 3-stage deliberation.
   * Creates per-conversation stream tracking so the process continues if user switches away.
   *
   * Includes safeguards:
   * - Max simultaneous streams limit (MAX_SIMULTANEOUS_STREAMS)
   * - Stream timeout (STREAM_TIMEOUT_MS) to prevent stuck UI during network issues
   *
   * @param {string} content - The user message content
   * @param {string|null} originalQuery - Original query before prompt improvement
   * @param {Object|null} completedStages - Previously completed stage data for smart retry
   */
  const handleSendMessage = async (content, originalQuery = null, completedStages = null) => {
    // Track the conversation ID - may be null for draft conversations
    let conversationId = currentConversationId

    // Check if we've hit the max simultaneous streams limit
    // (Exclude the current conversation since we'll abort its stream if active)
    const activeStreamCount = streamControllersRef.current.size
    const isCurrentActive = conversationId && streamControllersRef.current.has(conversationId)
    const effectiveStreamCount = isCurrentActive ? activeStreamCount - 1 : activeStreamCount

    if (effectiveStreamCount >= MAX_SIMULTANEOUS_STREAMS) {
      toast.warning('Too many active deliberations', {
        description: `Please wait for an existing conversation to finish. Maximum ${MAX_SIMULTANEOUS_STREAMS} simultaneous streams allowed.`,
      })
      return
    }

    try {
      // If no conversation exists yet (draft), create one first
      if (!conversationId) {
        setIsCreatingConversation(true)
        try {
          const newConv = await api.createConversation()
          conversationId = newConv.id
          // Add to conversation list (using hook function)
          addConversation({
            id: newConv.id,
            created_at: newConv.created_at,
            title: newConv.title,
            message_count: 0,
          })
          // Update current conversation with the new ID
          setCurrentConversationId(newConv.id)
          setCurrentConversation((prev) => ({
            ...prev,
            id: newConv.id,
          }))
        } catch (error) {
          console.error('Failed to create conversation:', error)
          if (!isConnectionError(error)) {
            toast.error('Failed to create conversation. Please try again.')
          }
          setIsCreatingConversation(false)
          return // Exit early if we can't create the conversation
        } finally {
          setIsCreatingConversation(false)
        }
      }

      // If this conversation already has an active stream, abort it first
      if (streamControllersRef.current.has(conversationId)) {
        abortStream(conversationId)
      }

      // If this conversation is being polled (recovery mode), stop polling
      // since we're starting a fresh stream that will provide real-time updates
      if (pollingIntervalsRef.current.has(conversationId)) {
        stopPolling(conversationId)
      }

      // Create new AbortController for this conversation
      const controller = new AbortController()
      streamControllersRef.current.set(conversationId, controller)

      // Set up stream timeout - auto-abort if no events received within timeout
      const timeoutConvId = conversationId // Capture for closure
      const timeoutId = setTimeout(() => {
        if (streamControllersRef.current.has(timeoutConvId)) {
          console.warn(`Stream timeout for conversation ${timeoutConvId}`)

          // Capture completed stage data before clearing (same pattern as error handler)
          let completedStagesOnTimeout = { stage1: null, stage2: null, stage2Metadata: null }
          setConversationStreams(prev => {
            const streamState = prev[timeoutConvId]
            if (streamState?.conversation?.messages?.length) {
              const messages = streamState.conversation.messages
              const lastMsg = messages[messages.length - 1]
              if (lastMsg?.role === 'assistant') {
                if (lastMsg.stage1) {
                  completedStagesOnTimeout.stage1 = lastMsg.stage1
                } else if (streamState.partialStage1Responses?.length > 0) {
                  // Stage 1 didn't complete, but we have partial responses
                  console.log('[SmartRetry] Timeout: Capturing partial Stage 1 responses:', streamState.partialStage1Responses.length)
                  completedStagesOnTimeout.stage1 = streamState.partialStage1Responses
                }
                if (lastMsg.stage2) {
                  completedStagesOnTimeout.stage2 = lastMsg.stage2
                  completedStagesOnTimeout.stage2Metadata = lastMsg.metadata || null
                }
              }
            } else if (streamState?.partialStage1Responses?.length > 0) {
              // No messages yet but we have partial responses (edge case)
              console.log('[SmartRetry] Timeout: Capturing partial Stage 1 responses (no messages):', streamState.partialStage1Responses.length)
              completedStagesOnTimeout.stage1 = streamState.partialStage1Responses
            }
            return prev // No state change, just reading
          })

          // Update stream state with timeout error AND completed stages for smart retry
          updateStreamState(timeoutConvId, prev => ({
            isLoading: false,
            error: {
              message: 'Deliberation timed out. The server may be overloaded or your connection was interrupted.',
              content,
              originalQuery,
              completedStages: completedStagesOnTimeout,
            },
          }))
          // Abort the stream and cleanup
          abortStream(timeoutConvId)
          toast.error('Deliberation timed out', {
            description: 'Please check your connection and try again.',
          })
        }
      }, STREAM_TIMEOUT_MS)
      streamTimeoutsRef.current.set(conversationId, timeoutId)

      // Prepare messages
      const userMessage = { role: 'user', content }
      const assistantMessage = {
        role: 'assistant',
        stage1: null,
        stage2: null,
        stage3: null,
        metadata: null,
        loading: {
          stage1: true,
          stage2: false,
          stage3: false,
        },
      }

      // Build initial conversation state with messages
      const updatedConversation = {
        ...currentConversation,
        id: conversationId,
        messages: [...currentConversation.messages, userMessage, assistantMessage],
      }

      // Initialize stream state for this conversation
      const initialStreamState = createInitialStreamState(updatedConversation)
      setConversationStreams(prev => ({
        ...prev,
        [conversationId]: initialStreamState,
      }))

      // Also update current conversation immediately for responsive UI
      setCurrentConversation(updatedConversation)

      // Start streaming - events will update the stream state for this specific conversation
      await api.sendMessageStream(conversationId, content, (eventType, event) => {
        // Reset timeout on each event (stream is alive)
        clearStreamTimeout(conversationId)
        const newTimeoutId = setTimeout(() => {
          if (streamControllersRef.current.has(conversationId)) {
            console.warn(`Stream timeout for conversation ${conversationId}`)

            // Capture completed stage data before clearing (same pattern as initial timeout)
            let completedStagesOnEventTimeout = { stage1: null, stage2: null, stage2Metadata: null }
            setConversationStreams(prev => {
              const streamState = prev[conversationId]
              if (streamState?.conversation?.messages?.length) {
                const messages = streamState.conversation.messages
                const lastMsg = messages[messages.length - 1]
                if (lastMsg?.role === 'assistant') {
                  if (lastMsg.stage1) {
                    completedStagesOnEventTimeout.stage1 = lastMsg.stage1
                  } else if (streamState.partialStage1Responses?.length > 0) {
                    console.log('[SmartRetry] Event timeout: Capturing partial Stage 1 responses:', streamState.partialStage1Responses.length)
                    completedStagesOnEventTimeout.stage1 = streamState.partialStage1Responses
                  }
                  if (lastMsg.stage2) {
                    completedStagesOnEventTimeout.stage2 = lastMsg.stage2
                    completedStagesOnEventTimeout.stage2Metadata = lastMsg.metadata || null
                  }
                }
              } else if (streamState?.partialStage1Responses?.length > 0) {
                console.log('[SmartRetry] Event timeout: Capturing partial Stage 1 responses (no messages):', streamState.partialStage1Responses.length)
                completedStagesOnEventTimeout.stage1 = streamState.partialStage1Responses
              }
              return prev // No state change, just reading
            })

            updateStreamState(conversationId, () => ({
              isLoading: false,
              error: {
                message: 'Deliberation timed out. The server may be overloaded or your connection was interrupted.',
                content,
                originalQuery,
                completedStages: completedStagesOnEventTimeout,
              },
            }))
            abortStream(conversationId)
            toast.error('Deliberation timed out', {
              description: 'Please check your connection and try again.',
            })
          }
        }, STREAM_TIMEOUT_MS)
        streamTimeoutsRef.current.set(conversationId, newTimeoutId)

        handleStreamEvent(conversationId, eventType, event, content, originalQuery)
      }, { originalQuery, signal: controller.signal, completedStages })

    } catch (error) {
      if (error.name === 'AbortError') {
        console.log(`Stream for conversation ${conversationId} was aborted`)
        return
      }

      console.error('Failed to send message:', error)
      if (isMountedRef.current && conversationId) {
        // Clean up timeout on error
        clearStreamTimeout(conversationId)

        // Capture completed stage data before clearing (same pattern as error handler)
        let completedStagesOnCatch = { stage1: null, stage2: null, stage2Metadata: null }
        setConversationStreams(prev => {
          const streamState = prev[conversationId]
          if (streamState?.conversation?.messages?.length) {
            const messages = streamState.conversation.messages
            const lastMsg = messages[messages.length - 1]
            if (lastMsg?.role === 'assistant') {
              if (lastMsg.stage1) {
                completedStagesOnCatch.stage1 = lastMsg.stage1
              } else if (streamState.partialStage1Responses?.length > 0) {
                console.log('[SmartRetry] Catch: Capturing partial Stage 1 responses:', streamState.partialStage1Responses.length)
                completedStagesOnCatch.stage1 = streamState.partialStage1Responses
              }
              if (lastMsg.stage2) {
                completedStagesOnCatch.stage2 = lastMsg.stage2
                completedStagesOnCatch.stage2Metadata = lastMsg.metadata || null
              }
            }
          } else if (streamState?.partialStage1Responses?.length > 0) {
            console.log('[SmartRetry] Catch: Capturing partial Stage 1 responses (no messages):', streamState.partialStage1Responses.length)
            completedStagesOnCatch.stage1 = streamState.partialStage1Responses
          }
          return prev // No state change, just reading
        })

        // Update stream state with error AND completed stages for smart retry
        updateStreamState(conversationId, prev => ({
          isLoading: false,
          error: {
            message: error.message || 'Failed to send message',
            content,
            originalQuery,
            completedStages: completedStagesOnCatch,
          },
          // Remove the pending messages on error
          conversation: prev?.conversation ? {
            ...prev.conversation,
            messages: prev.conversation.messages.slice(0, -2),
          } : null,
        }))

        // Skip toast for connection errors - the ConnectionErrorBanner handles those
        if (!isConnectionError(error)) {
          toast.error('Failed to send message. Please try again.')
        }
      }
    }
  }

  // ============================================================================
  // STREAM EVENT HANDLERS (extracted for maintainability)
  // ============================================================================

  /**
   * Helper to update the last assistant message in a conversation's stream state.
   * @param {string} conversationId - The conversation to update
   * @param {function} updater - Function that receives the last message and returns updated message
   */
  const updateLastAssistantMessage = useCallback((conversationId, updater) => {
    updateStreamConversation(conversationId, (conv) => {
      if (!conv?.messages?.length) return conv
      const messages = [...conv.messages]
      const lastMsg = messages[messages.length - 1]
      if (lastMsg?.role === 'assistant') {
        messages[messages.length - 1] = updater(lastMsg)
      }
      return { ...conv, messages }
    })
  }, [updateStreamConversation])

  /**
   * Individual event handlers, keyed by event type.
   * Each handler receives: (conversationId, event, helpers)
   * where helpers = { content, originalQuery } for retry information
   */
  const streamEventHandlers = useMemo(() => ({
    stage1_start: (conversationId, event) => {
      updateStreamState(conversationId, prev => {
        const modelStatuses = {}
        if (event.models) {
          event.models.forEach((model) => {
            modelStatuses[model] = 'processing'
          })
        }
        return {
          modelStatuses,
          stageTimings: {
            ...prev.stageTimings,
            stage1: { startTime: Date.now(), elapsed: 0, completed: false },
          },
        }
      })
      updateLastAssistantMessage(conversationId, msg => ({
        ...msg,
        loading: { ...msg.loading, stage1: true },
      }))
    },

    model_response: (conversationId, event) => {
      updateStreamState(conversationId, prev => {
        const updates = {
          modelStatuses: {
            ...prev.modelStatuses,
            [event.model]: event.success ? 'received' : 'failed',
          },
          modelTimings: {
            ...prev.modelTimings,
            [event.model]: event.elapsed_ms,
          },
        }
        // Accumulate successful responses for smart retry (in case Stage 1 fails mid-way)
        if (event.success && event.response_content) {
          updates.partialStage1Responses = [
            ...prev.partialStage1Responses,
            { model: event.model, response: event.response_content },
          ]
        }
        return updates
      })
    },

    stage1_complete: (conversationId, event) => {
      markStageCompleted(conversationId, 'stage1')
      updateLastAssistantMessage(conversationId, msg => ({
        ...msg,
        stage1: event.data,
        loading: { ...msg.loading, stage1: false },
      }))
    },

    // Smart retry: Stage 1 was skipped (reusing data from previous attempt)
    stage1_skipped: (conversationId, event) => {
      console.log('[SmartRetry] Stage 1 skipped, reusing', event.data?.length, 'cached responses')
      markStageCompleted(conversationId, 'stage1')
      updateLastAssistantMessage(conversationId, msg => ({
        ...msg,
        stage1: event.data,
        loading: { ...msg.loading, stage1: false },
      }))
      // Show toast to inform user we're reusing data
      toast.info('Reusing model responses from previous attempt', { duration: 2000 })
    },

    stage2_start: (conversationId) => {
      updateStreamState(conversationId, prev => ({
        stageTimings: {
          ...prev.stageTimings,
          stage2: { startTime: Date.now(), elapsed: 0, completed: false },
        },
      }))
      updateLastAssistantMessage(conversationId, msg => ({
        ...msg,
        loading: { ...msg.loading, stage2: true },
      }))
    },

    stage2_complete: (conversationId, event) => {
      markStageCompleted(conversationId, 'stage2')
      updateLastAssistantMessage(conversationId, msg => ({
        ...msg,
        stage2: event.data,
        metadata: event.metadata,
        loading: { ...msg.loading, stage2: false },
      }))
    },

    // Smart retry: Stage 2 was skipped (reusing data from previous attempt)
    stage2_skipped: (conversationId, event) => {
      console.log('[SmartRetry] Stage 2 skipped, reusing cached rankings')
      markStageCompleted(conversationId, 'stage2')
      updateLastAssistantMessage(conversationId, msg => ({
        ...msg,
        stage2: event.data,
        metadata: event.metadata,
        loading: { ...msg.loading, stage2: false },
      }))
      // Show toast to inform user we're reusing data
      toast.info('Reusing peer rankings from previous attempt', { duration: 2000 })
    },

    stage3_start: (conversationId) => {
      updateStreamState(conversationId, prev => ({
        stageTimings: {
          ...prev.stageTimings,
          stage3: { startTime: Date.now(), elapsed: 0, completed: false },
        },
      }))
      updateLastAssistantMessage(conversationId, msg => ({
        ...msg,
        loading: { ...msg.loading, stage3: true },
      }))
    },

    stage3_complete: (conversationId, event) => {
      markStageCompleted(conversationId, 'stage3')
      updateLastAssistantMessage(conversationId, msg => ({
        ...msg,
        stage3: event.data,
        loading: { ...msg.loading, stage3: false },
      }))
    },

    title_complete: () => {
      // Refresh conversation list to show new title
      loadConversations()
    },

    complete: (conversationId) => {
      // Check if this completed in the background (user switched away)
      // Use ref to get current value at event time, not stale closure value
      const isBackground = currentConversationIdRef.current !== conversationId

      // Clean up stream state - the data is preserved in the conversation
      cleanupStream(conversationId)

      // Refresh conversation list
      loadConversations()

      // If completed in background, show a toast notification
      if (isBackground) {
        toast.success('Background deliberation completed', {
          description: 'A conversation finished processing in the background.',
          action: {
            label: 'View',
            onClick: () => setCurrentConversationId(conversationId),
          },
        })
      }
    },

    error: async (conversationId, event, { content, originalQuery }) => {
      console.error('Stream error:', event.message, 'Stage:', event.stage || 'unknown')

      // Use ref to get current value at event time, not stale closure value
      const isBackground = currentConversationIdRef.current !== conversationId

      // Capture completed stage data from the incomplete message BEFORE removing it
      // This enables smart retry: we can reuse completed stages instead of starting over
      let completedStages = { stage1: null, stage2: null, stage2Metadata: null }

      // If the error event includes stage1_data (e.g., Stage 2 failed after Stage 1 completed),
      // use it directly from the event - this is the most reliable source
      if (event.stage1_data) {
        console.log('[SmartRetry] Using stage1_data from error event:', event.stage1_data.length, 'responses')
        completedStages.stage1 = event.stage1_data
      }

      // If the error event includes response_id, fetch partial data from backend
      // This is the most reliable source for smart retry as it's persisted to DB
      if (event.response_id) {
        console.log('[SmartRetry] Fetching partial stages from backend for response:', event.response_id)
        try {
          const partialData = await api.getPartialStages(event.response_id)
          if (partialData) {
            // Use persisted stage data if available
            if (partialData.stage1_responses && !completedStages.stage1) {
              console.log('[SmartRetry] Using stage1_responses from backend:', partialData.stage1_responses.length)
              completedStages.stage1 = partialData.stage1_responses
            }
            if (partialData.stage2_evaluations && !completedStages.stage2) {
              console.log('[SmartRetry] Using stage2_evaluations from backend')
              completedStages.stage2 = partialData.stage2_evaluations
              completedStages.stage2Metadata = partialData.metadata || null
            }
            // Also check partial_stages for individual model responses (Stage 1 failed mid-way)
            if (!completedStages.stage1 && partialData.partial_stages?.[1]?.length > 0) {
              const successfulResponses = partialData.partial_stages[1]
                .filter(r => r.status === 'success')
                .map(r => ({
                  model: r.model_name,
                  response: r.response_content?.content || r.response_content,
                }))
              if (successfulResponses.length > 0) {
                console.log('[SmartRetry] Using partial Stage 1 responses from backend:', successfulResponses.length)
                completedStages.stage1 = successfulResponses
              }
            }
          }
        } catch (err) {
          console.warn('[SmartRetry] Failed to fetch partial stages from backend:', err)
          // Fall through to in-memory fallback
        }
      }

      // Fallback: Extract completed stage data from the current stream state's conversation
      setConversationStreams(prev => {
        const streamState = prev[conversationId]
        if (streamState?.conversation?.messages?.length) {
          const messages = streamState.conversation.messages
          const lastMsg = messages[messages.length - 1]
          if (lastMsg?.role === 'assistant') {
            // Capture any completed stage data (only if not already set from event or backend)
            if (!completedStages.stage1) {
              if (lastMsg.stage1) {
                completedStages.stage1 = lastMsg.stage1
              } else if (streamState.partialStage1Responses?.length > 0) {
                // Stage 1 didn't complete, but we have partial responses from model_response events
                // Use these for smart retry so we don't lose successful model responses
                console.log('[SmartRetry] Capturing partial Stage 1 responses from memory:', streamState.partialStage1Responses.length)
                completedStages.stage1 = streamState.partialStage1Responses
              }
            }
            if (!completedStages.stage2 && lastMsg.stage2) {
              completedStages.stage2 = lastMsg.stage2
              completedStages.stage2Metadata = lastMsg.metadata || null
            }
          }
        } else if (!completedStages.stage1 && streamState?.partialStage1Responses?.length > 0) {
          // No messages yet but we have partial responses (edge case)
          console.log('[SmartRetry] Capturing partial Stage 1 responses from memory (no messages):', streamState.partialStage1Responses.length)
          completedStages.stage1 = streamState.partialStage1Responses
        }
        return prev // No changes to state, just reading
      })

      // Update stream state with error AND completed stage data for retry
      updateStreamState(conversationId, () => ({
        isLoading: false,
        error: {
          message: event.message || 'An error occurred while processing your request.',
          content,
          originalQuery,
          // Include completed stages for smart retry
          completedStages,
        },
      }))

      // Remove the incomplete assistant message
      updateStreamConversation(conversationId, (conv) => {
        if (!conv?.messages?.length) return conv
        const messages = [...conv.messages]
        const lastMsg = messages[messages.length - 1]
        if (lastMsg?.role === 'assistant' && (lastMsg.loading || !lastMsg.stage3)) {
          messages.pop()
        }
        return { ...conv, messages }
      })

      // Remove controller (but keep stream state for error display)
      streamControllersRef.current.delete(conversationId)

      // Show toast - indicate if it was a background error
      if (isBackground) {
        toast.error('Background deliberation failed', {
          description: event.message,
          action: {
            label: 'View',
            onClick: () => setCurrentConversationId(conversationId),
          },
        })
      } else {
        toast.error(`Deliberation failed: ${event.message}`)
      }
    },
  }), [updateStreamState, updateLastAssistantMessage, markStageCompleted, cleanupStream, updateStreamConversation])

  /**
   * Handle stream events for a specific conversation.
   * All updates are made to conversationStreams[conversationId], which preserves
   * state even when the user is viewing a different conversation.
   *
   * @param {string} conversationId - The conversation this event belongs to
   * @param {string} eventType - The type of SSE event
   * @param {Object} event - The event data
   * @param {string} content - Original message content (for retry)
   * @param {string|null} originalQuery - Original query before improvement
   */
  const handleStreamEvent = useCallback((conversationId, eventType, event, content, originalQuery) => {
    // Early return if component is unmounted - prevents React state updates after unmount
    if (!isMountedRef.current) {
      console.log(`Ignoring ${eventType} event for ${conversationId} - component unmounted`)
      return
    }

    // Update lastEventTime for stale stream detection
    updateStreamState(conversationId, { lastEventTime: Date.now() })

    // Look up and invoke the appropriate handler
    const handler = streamEventHandlers[eventType]
    if (handler) {
      handler(conversationId, event, { content, originalQuery })
    } else {
      console.log('Unknown event type:', eventType, 'for conversation:', conversationId)
    }
  }, [streamEventHandlers, updateStreamState])

  // ============================================================================
  // RENDER
  // ============================================================================

  // Create a Map of processing conversation IDs for sidebar indicator
  const processingConversations = useMemo(() => {
    const map = new Map()
    for (const [convId, streamState] of Object.entries(conversationStreams)) {
      if (streamState.isLoading) {
        map.set(convId, true)
      }
    }
    return map
  }, [conversationStreams])

  return (
    <div className="flex h-full overflow-hidden">
      <ConversationSidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        processingConversations={processingConversations}
        isLoadingConversations={isLoadingConversations}
        isLoadingMore={isLoadingMore}
        hasMore={hasMoreConversations}
        onLoadMore={loadMoreConversations}
      />
      <ChatInterface
        conversation={activeConversation}
        onSendMessage={handleSendMessage}
        isCreatingConversation={isCreatingConversation}
        // Grouped streaming state
        streamingState={{
          isLoading,
          stageTimings,
          modelStatuses,
          modelTimings,
        }}
        // Grouped error handlers
        errorHandlers={{
          currentError,
          onRetry: handleRetryMessage,
          onClearError: handleClearError,
          onCancelStream: handleCancelStream,
        }}
        // Grouped polling state for recovery after browser refresh
        pollingState={{
          status: currentConversationId ? pollingConversations[currentConversationId]?.status : null,
          responseId: currentConversationId ? pollingConversations[currentConversationId]?.responseId : null,
          onStop: currentConversationId ? () => stopPolling(currentConversationId) : null,
          onCancel: currentConversationId ? (responseId) => handleCancelDeliberation(currentConversationId, responseId) : null,
          isCancelling: currentConversationId ? !!cancellingConversations[currentConversationId] : false,
        }}
        // Grouped resume state
        resumeState={{
          onResume: handleResumeDeliberation,
          resumingId: Object.keys(resumingResponses).find(id => resumingResponses[id]) || null,
        }}
      />
    </div>
  )
}
