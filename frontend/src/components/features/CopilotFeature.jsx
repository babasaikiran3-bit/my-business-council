import { useState, useEffect, useRef } from 'react'
import { useAuth } from '@workos-inc/authkit-react'
import { toast } from 'sonner'
import { api } from '../../api'
import { isConnectionError } from '@/contexts/ConnectionErrorContext'
import ConversationSidebar from './copilot/ConversationSidebar'
import ChatInterface from '../ChatInterface'

/**
 * CopilotFeature - The 3-stage LLM deliberation feature.
 * This wraps the existing Copilot functionality for use within the dashboard.
 */
export default function CopilotFeature() {
  const { getAccessToken } = useAuth()

  const [conversations, setConversations] = useState([])
  const [currentConversationId, setCurrentConversationId] = useState(null)
  const [currentConversation, setCurrentConversation] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  // Error state for current conversation with retry info
  const [currentError, setCurrentError] = useState(null)

  // Track stage timings - stores start times and elapsed times
  const [stageTimings, setStageTimings] = useState({
    stage1: { startTime: null, elapsed: 0, completed: false },
    stage2: { startTime: null, elapsed: 0, completed: false },
    stage3: { startTime: null, elapsed: 0, completed: false },
  })

  // Track individual model statuses: 'pending' | 'processing' | 'received' | 'failed'
  const [modelStatuses, setModelStatuses] = useState({})

  // Track individual model response times in milliseconds
  const [modelTimings, setModelTimings] = useState({})

  // Timer interval ref for cleanup
  const timerIntervalRef = useRef(null)

  // Ref to hold latest stageTimings for interval callback
  const latestStageTimingsRef = useRef(stageTimings)

  // AbortController for stream cancellation
  const streamControllerRef = useRef(null)
  const isMountedRef = useRef(true)

  // Compute whether any stage is active
  const hasActiveStage = Object.values(stageTimings).some(
    (timing) => timing.startTime && !timing.completed
  )

  // Set auth token getter for API calls
  useEffect(() => {
    api.setTokenGetter(getAccessToken)
  }, [getAccessToken])

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      if (streamControllerRef.current) {
        streamControllerRef.current.abort()
      }
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current)
      }
    }
  }, [])

  // Load conversations on mount
  useEffect(() => {
    loadConversations()
  }, [])

  // Load conversation details when selected
  useEffect(() => {
    if (currentConversationId) {
      loadConversation(currentConversationId)
    }
  }, [currentConversationId])

  // Keep latestStageTimingsRef in sync with stageTimings
  useEffect(() => {
    latestStageTimingsRef.current = stageTimings
  }, [stageTimings])

  // Timer update effect
  useEffect(() => {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current)
      timerIntervalRef.current = null
    }

    if (hasActiveStage) {
      timerIntervalRef.current = setInterval(() => {
        const current = latestStageTimingsRef.current
        setStageTimings((prev) => {
          const updated = { ...prev }
          for (const stage of ['stage1', 'stage2', 'stage3']) {
            if (current[stage].startTime && !current[stage].completed) {
              updated[stage] = {
                ...prev[stage],
                elapsed: Date.now() - current[stage].startTime,
              }
            }
          }
          return updated
        })
      }, 500)
    }

    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current)
        timerIntervalRef.current = null
      }
    }
  }, [hasActiveStage])

  // Helper to reset progress state for new message
  const resetProgressState = () => {
    setStageTimings({
      stage1: { startTime: null, elapsed: 0, completed: false },
      stage2: { startTime: null, elapsed: 0, completed: false },
      stage3: { startTime: null, elapsed: 0, completed: false },
    })
    setModelStatuses({})
    setModelTimings({})
  }

  // Helper to mark a stage as completed
  const markStageCompleted = (stage) => {
    latestStageTimingsRef.current = {
      ...latestStageTimingsRef.current,
      [stage]: { ...latestStageTimingsRef.current[stage], completed: true },
    }
    setStageTimings((prev) => ({
      ...prev,
      [stage]: { ...prev[stage], completed: true },
    }))
  }

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations()
      setConversations(convs)
    } catch (error) {
      console.error('Failed to load conversations:', error)
      // Skip toast for connection errors - the ConnectionErrorBanner handles those
      if (!isConnectionError(error)) {
        toast.error('Failed to load conversations')
      }
    }
  }

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id)
      setCurrentConversation(conv)
    } catch (error) {
      console.error('Failed to load conversation:', error)
      // Skip toast for connection errors - the ConnectionErrorBanner handles those
      if (!isConnectionError(error)) {
        toast.error('Failed to load conversation')
      }
    }
  }

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation()
      setConversations((prev) => [
        { id: newConv.id, created_at: newConv.created_at, title: newConv.title, message_count: 0 },
        ...prev,
      ])
      setCurrentConversation(newConv)
      setCurrentConversationId(newConv.id)
      toast.success('New conversation created')
    } catch (error) {
      console.error('Failed to create conversation:', error)
      // Skip toast for connection errors - the ConnectionErrorBanner handles those
      if (!isConnectionError(error)) {
        toast.error('Failed to create conversation')
      }
    }
  }

  const handleSelectConversation = (id) => {
    if (streamControllerRef.current) {
      streamControllerRef.current.abort()
      streamControllerRef.current = null
      setIsLoading(false)
      resetProgressState()
    }
    setCurrentConversationId(id)
  }

  const handleClearError = () => {
    setCurrentError(null)
  }

  const handleRetryMessage = () => {
    if (!currentError) return
    const { content, originalQuery } = currentError
    setCurrentError(null)
    handleSendMessage(content, originalQuery)
  }

  const handleCancelStream = () => {
    if (streamControllerRef.current) {
      streamControllerRef.current.abort()
      streamControllerRef.current = null
      setIsLoading(false)
      resetProgressState()
      toast.info('Deliberation cancelled')
    }
  }

  const handleSendMessage = async (content, originalQuery = null) => {
    if (!currentConversationId) return

    setCurrentError(null)

    if (streamControllerRef.current) {
      streamControllerRef.current.abort()
    }

    const controller = new AbortController()
    streamControllerRef.current = controller

    setIsLoading(true)
    resetProgressState()

    try {
      const userMessage = { role: 'user', content }
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }))

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

      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }))

      await api.sendMessageStream(currentConversationId, content, (eventType, event) => {
        handleStreamEvent(eventType, event, content, originalQuery)
      }, { originalQuery, signal: controller.signal })
    } catch (error) {
      if (error.name === 'AbortError') {
        console.log('Stream was aborted')
        return
      }

      console.error('Failed to send message:', error)
      if (isMountedRef.current) {
        setCurrentConversation((prev) => ({
          ...prev,
          messages: prev.messages.slice(0, -2),
        }))
        // Skip toast for connection errors - the ConnectionErrorBanner handles those
        if (!isConnectionError(error)) {
          toast.error('Failed to send message. Please try again.')
        }
        setIsLoading(false)
      }
      streamControllerRef.current = null
    }
  }

  const handleStreamEvent = (eventType, event, content, originalQuery) => {
    switch (eventType) {
      case 'stage1_start':
        if (event.models) {
          const initialStatuses = {}
          event.models.forEach((model) => {
            initialStatuses[model] = 'processing'
          })
          setModelStatuses(initialStatuses)
        }
        setStageTimings((prev) => ({
          ...prev,
          stage1: { startTime: Date.now(), elapsed: 0, completed: false },
        }))
        setCurrentConversation((prev) => {
          const messages = [...prev.messages]
          const lastMsg = messages[messages.length - 1]
          messages[messages.length - 1] = {
            ...lastMsg,
            loading: { ...lastMsg.loading, stage1: true },
          }
          return { ...prev, messages }
        })
        break

      case 'model_response':
        setModelStatuses((prev) => ({
          ...prev,
          [event.model]: event.success ? 'received' : 'failed',
        }))
        setModelTimings((prev) => ({
          ...prev,
          [event.model]: event.elapsed_ms,
        }))
        break

      case 'stage1_complete':
        markStageCompleted('stage1')
        setCurrentConversation((prev) => {
          const messages = [...prev.messages]
          const lastMsg = messages[messages.length - 1]
          messages[messages.length - 1] = {
            ...lastMsg,
            stage1: event.data,
            loading: { ...lastMsg.loading, stage1: false },
          }
          return { ...prev, messages }
        })
        break

      case 'stage2_start':
        setStageTimings((prev) => ({
          ...prev,
          stage2: { startTime: Date.now(), elapsed: 0, completed: false },
        }))
        setCurrentConversation((prev) => {
          const messages = [...prev.messages]
          const lastMsg = messages[messages.length - 1]
          messages[messages.length - 1] = {
            ...lastMsg,
            loading: { ...lastMsg.loading, stage2: true },
          }
          return { ...prev, messages }
        })
        break

      case 'stage2_complete':
        markStageCompleted('stage2')
        setCurrentConversation((prev) => {
          const messages = [...prev.messages]
          const lastMsg = messages[messages.length - 1]
          messages[messages.length - 1] = {
            ...lastMsg,
            stage2: event.data,
            metadata: event.metadata,
            loading: { ...lastMsg.loading, stage2: false },
          }
          return { ...prev, messages }
        })
        break

      case 'stage3_start':
        setStageTimings((prev) => ({
          ...prev,
          stage3: { startTime: Date.now(), elapsed: 0, completed: false },
        }))
        setCurrentConversation((prev) => {
          const messages = [...prev.messages]
          const lastMsg = messages[messages.length - 1]
          messages[messages.length - 1] = {
            ...lastMsg,
            loading: { ...lastMsg.loading, stage3: true },
          }
          return { ...prev, messages }
        })
        break

      case 'stage3_complete':
        markStageCompleted('stage3')
        setCurrentConversation((prev) => {
          const messages = [...prev.messages]
          const lastMsg = messages[messages.length - 1]
          messages[messages.length - 1] = {
            ...lastMsg,
            stage3: event.data,
            loading: { ...lastMsg.loading, stage3: false },
          }
          return { ...prev, messages }
        })
        break

      case 'title_complete':
        loadConversations()
        break

      case 'complete':
        if (isMountedRef.current) {
          loadConversations()
          setIsLoading(false)
        }
        streamControllerRef.current = null
        break

      case 'error':
        console.error('Stream error:', event.message)
        if (isMountedRef.current) {
          toast.error(`Deliberation failed: ${event.message}`)
          setIsLoading(false)

          setCurrentError({
            message: event.message || 'An error occurred while processing your request.',
            content,
            originalQuery,
          })

          setCurrentConversation((prev) => {
            if (!prev) return prev
            const messages = [...prev.messages]
            const lastMsg = messages[messages.length - 1]
            if (lastMsg?.role === 'assistant' && (lastMsg.loading || !lastMsg.stage3)) {
              messages.pop()
            }
            return { ...prev, messages }
          })
        }
        streamControllerRef.current = null
        break

      default:
        console.log('Unknown event type:', eventType)
    }
  }

  return (
    <div className="flex h-full overflow-hidden">
      <ConversationSidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        stageTimings={stageTimings}
        modelStatuses={modelStatuses}
        modelTimings={modelTimings}
        currentError={currentError}
        onRetry={handleRetryMessage}
        onClearError={handleClearError}
        onCancelStream={handleCancelStream}
      />
    </div>
  )
}
