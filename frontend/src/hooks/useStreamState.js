/**
 * Custom hook for managing per-conversation stream state.
 * Handles tracking multiple simultaneous conversation streams.
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import { DEFAULT_STAGE_TIMINGS } from './useStageTimings'

// Timeout for streams that receive no events (prevents stuck UI during network issues)
// Set to 8 minutes to accommodate slow models like openai/gpt-5.2-pro which can take 6+ minutes.
// IMPORTANT: This is the single source of truth for stream timeout configuration.
// Both STREAM_TIMEOUT_MS and STALE_THRESHOLD_MS use this value to ensure consistent behavior.
export const STREAM_TIMEOUT_MS = 480000 // 8 minutes

// Maximum number of simultaneous streams to prevent resource exhaustion
export const MAX_SIMULTANEOUS_STREAMS = 5

// How often to check for stale streams (30 seconds)
export const STALE_CHECK_INTERVAL_MS = 30000

// How long a stream can go without events before being considered stale.
// Uses STREAM_TIMEOUT_MS as the single source of truth for timeout configuration.
export const STALE_THRESHOLD_MS = STREAM_TIMEOUT_MS

/**
 * Creates a fresh stream state object for a conversation.
 * @param {Object} conversation - The conversation object to associate with this stream
 * @returns {Object} Initial stream state
 */
export const createInitialStreamState = (conversation) => ({
  isLoading: true,
  stageTimings: { ...DEFAULT_STAGE_TIMINGS },
  modelStatuses: {},
  modelTimings: {},
  partialStage1Responses: [],
  error: null,
  conversation: conversation ? { ...conversation } : null,
  lastEventTime: Date.now(),
})

/**
 * Hook for managing per-conversation streaming state.
 * Supports multiple simultaneous streams with proper cleanup.
 *
 * @returns {Object} Stream state and operations
 */
export function useStreamState() {
  const [conversationStreams, setConversationStreams] = useState({})
  const streamControllersRef = useRef(new Map())
  const streamTimeoutsRef = useRef(new Map())
  const isMountedRef = useRef(true)

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      streamControllersRef.current.forEach((controller) => {
        controller.abort()
      })
      streamControllersRef.current.clear()
      streamTimeoutsRef.current.forEach((timeoutId) => {
        clearTimeout(timeoutId)
      })
      streamTimeoutsRef.current.clear()
    }
  }, [])

  // Periodic cleanup for stale streams
  useEffect(() => {
    const cleanupInterval = setInterval(() => {
      const now = Date.now()

      setConversationStreams(prev => {
        const updated = { ...prev }
        let hasChanges = false

        for (const [convId, streamState] of Object.entries(prev)) {
          if (!streamState.isLoading) continue

          const timeSinceLastEvent = now - (streamState.lastEventTime || 0)
          if (timeSinceLastEvent > STALE_THRESHOLD_MS) {
            console.warn(`Cleaning up stale stream: ${convId}`)
            updated[convId] = {
              ...streamState,
              isLoading: false,
              error: {
                message: 'The deliberation appears to have stalled. Please try again.',
                content: '',
                originalQuery: null,
              },
            }
            const controller = streamControllersRef.current.get(convId)
            if (controller) controller.abort()
            streamControllersRef.current.delete(convId)
            clearTimeout(streamTimeoutsRef.current.get(convId))
            streamTimeoutsRef.current.delete(convId)
            hasChanges = true
          }
        }
        return hasChanges ? updated : prev
      })
    }, STALE_CHECK_INTERVAL_MS)

    return () => clearInterval(cleanupInterval)
  }, [])

  /**
   * Update stream state for a conversation.
   */
  const updateStreamState = useCallback((conversationId, updater) => {
    setConversationStreams(prev => {
      const currentState = prev[conversationId]
      if (!currentState) return prev
      const updates = typeof updater === 'function' ? updater(currentState) : updater
      return { ...prev, [conversationId]: { ...currentState, ...updates } }
    })
  }, [])

  /**
   * Update conversation data within a stream state.
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
   * Initialize a new stream for a conversation.
   */
  const initializeStream = useCallback((conversationId, conversation, controller) => {
    streamControllersRef.current.set(conversationId, controller)
    setConversationStreams(prev => ({
      ...prev,
      [conversationId]: createInitialStreamState(conversation)
    }))
  }, [])

  /**
   * Clean up a stream.
   */
  const cleanupStream = useCallback((conversationId) => {
    setConversationStreams(prev => {
      const { [conversationId]: removed, ...rest } = prev
      return rest
    })
    streamControllersRef.current.delete(conversationId)
    clearTimeout(streamTimeoutsRef.current.get(conversationId))
    streamTimeoutsRef.current.delete(conversationId)
  }, [])

  /**
   * Abort and clean up a stream.
   */
  const abortStream = useCallback((conversationId) => {
    const controller = streamControllersRef.current.get(conversationId)
    if (controller) controller.abort()
    cleanupStream(conversationId)
  }, [cleanupStream])

  return {
    conversationStreams,
    streamControllersRef,
    streamTimeoutsRef,
    isMountedRef,
    updateStreamState,
    updateStreamConversation,
    initializeStream,
    cleanupStream,
    abortStream,
  }
}

