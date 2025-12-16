import { useState, useEffect, useRef } from 'react';
import { Routes, Route } from 'react-router-dom';
import { useAuth } from '@workos-inc/authkit-react';
import { AuthGuard } from './components/AuthGuard';
import { Callback } from './components/Callback';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import UserMenu from './components/UserMenu';
import { api } from './api';

function App() {
  return (
    <Routes>
      {/* OAuth callback route - must be outside AuthGuard */}
      <Route path="/callback" element={<Callback />} />

      {/* All other routes require authentication */}
      <Route path="/*" element={
        <AuthGuard>
          <AuthenticatedApp />
        </AuthGuard>
      } />
    </Routes>
  );
}

function AuthenticatedApp() {
  const { getAccessToken } = useAuth();

  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  // Track stage timings - stores start times and elapsed times
  const [stageTimings, setStageTimings] = useState({
    stage1: { startTime: null, elapsed: 0, completed: false },
    stage2: { startTime: null, elapsed: 0, completed: false },
    stage3: { startTime: null, elapsed: 0, completed: false },
  });

  // Track individual model statuses: 'pending' | 'processing' | 'received' | 'failed'
  const [modelStatuses, setModelStatuses] = useState({});

  // Track individual model response times in milliseconds
  const [modelTimings, setModelTimings] = useState({});

  // Timer interval ref for cleanup
  const timerIntervalRef = useRef(null);

  // Ref to hold latest stageTimings for interval callback
  const latestStageTimingsRef = useRef(stageTimings);

  // Compute whether any stage is active
  const hasActiveStage = Object.values(stageTimings).some(
    (timing) => timing.startTime && !timing.completed
  );

  // Set auth token getter for API calls
  useEffect(() => {
    api.setTokenGetter(getAccessToken);
  }, [getAccessToken]);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Load conversation details when selected
  useEffect(() => {
    if (currentConversationId) {
      loadConversation(currentConversationId);
    }
  }, [currentConversationId]);

  // Keep latestStageTimingsRef in sync with stageTimings
  useEffect(() => {
    latestStageTimingsRef.current = stageTimings;
  }, [stageTimings]);

  // Timer update effect - updates elapsed time every 100ms while stages are in progress
  useEffect(() => {
    if (hasActiveStage) {
      timerIntervalRef.current = setInterval(() => {
        const current = latestStageTimingsRef.current;
        setStageTimings((prev) => {
          const updated = { ...prev };
          for (const stage of ['stage1', 'stage2', 'stage3']) {
            if (current[stage].startTime && !current[stage].completed) {
              updated[stage] = {
                ...prev[stage],
                elapsed: Date.now() - current[stage].startTime,
              };
            }
          }
          return updated;
        });
      }, 100);
    }

    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
    };
  }, [hasActiveStage]);

  // Helper to reset progress state for new message
  const resetProgressState = () => {
    setStageTimings({
      stage1: { startTime: null, elapsed: 0, completed: false },
      stage2: { startTime: null, elapsed: 0, completed: false },
      stage3: { startTime: null, elapsed: 0, completed: false },
    });
    setModelStatuses({});
    setModelTimings({});
  };

  // Helper to mark a stage as completed
  // Updates ref synchronously to prevent timer race condition, then updates state
  const markStageCompleted = (stage) => {
    latestStageTimingsRef.current = {
      ...latestStageTimingsRef.current,
      [stage]: { ...latestStageTimingsRef.current[stage], completed: true },
    };
    setStageTimings((prev) => ({
      ...prev,
      [stage]: { ...prev[stage], completed: true },
    }));
  };

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      // Use functional update to avoid stale closure issue with conversations
      setConversations((prev) => [
        { id: newConv.id, created_at: newConv.created_at, title: newConv.title, message_count: 0 },
        ...prev,
      ]);
      // Set the conversation directly from the create response
      // This is more efficient than relying on a separate fetch via useEffect
      setCurrentConversation(newConv);
      setCurrentConversationId(newConv.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = (id) => {
    setCurrentConversationId(id);
  };

  const handleSendMessage = async (content, originalQuery = null) => {
    if (!currentConversationId) return;

    setIsLoading(true);
    resetProgressState();

    try {
      // Optimistically add user message to UI
      const userMessage = { role: 'user', content };
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }));

      // Create a partial assistant message that will be updated progressively
      // Start with stage1 loading true so the loading indicator shows immediately
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
      };

      // Add the partial assistant message
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      // Send message with streaming (pass originalQuery if prompt was improved)
      await api.sendMessageStream(currentConversationId, content, (eventType, event) => {
        switch (eventType) {
          case 'stage1_start':
            // Initialize model statuses from the models list
            if (event.models) {
              const initialStatuses = {};
              event.models.forEach((model) => {
                initialStatuses[model] = 'processing';
              });
              setModelStatuses(initialStatuses);
            }
            // Start stage 1 timer
            setStageTimings((prev) => ({
              ...prev,
              stage1: { startTime: Date.now(), elapsed: 0, completed: false },
            }));
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              messages[messages.length - 1] = {
                ...lastMsg,
                loading: { ...lastMsg.loading, stage1: true },
              };
              return { ...prev, messages };
            });
            break;

          case 'model_response':
            // Update individual model status
            setModelStatuses((prev) => ({
              ...prev,
              [event.model]: event.success ? 'received' : 'failed',
            }));
            // Store individual model response time
            setModelTimings((prev) => ({
              ...prev,
              [event.model]: event.elapsed_ms,
            }));
            break;

          case 'stage1_complete':
            // Mark stage 1 as completed (updates ref synchronously to prevent timer race condition)
            markStageCompleted('stage1');
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              messages[messages.length - 1] = {
                ...lastMsg,
                stage1: event.data,
                loading: { ...lastMsg.loading, stage1: false },
              };
              return { ...prev, messages };
            });
            break;

          case 'stage2_start':
            // Start stage 2 timer
            setStageTimings((prev) => ({
              ...prev,
              stage2: { startTime: Date.now(), elapsed: 0, completed: false },
            }));
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              messages[messages.length - 1] = {
                ...lastMsg,
                loading: { ...lastMsg.loading, stage2: true },
              };
              return { ...prev, messages };
            });
            break;

          case 'stage2_complete':
            // Mark stage 2 as completed (updates ref synchronously to prevent timer race condition)
            markStageCompleted('stage2');
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              messages[messages.length - 1] = {
                ...lastMsg,
                stage2: event.data,
                metadata: event.metadata,
                loading: { ...lastMsg.loading, stage2: false },
              };
              return { ...prev, messages };
            });
            break;

          case 'stage3_start':
            // Start stage 3 timer
            setStageTimings((prev) => ({
              ...prev,
              stage3: { startTime: Date.now(), elapsed: 0, completed: false },
            }));
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              messages[messages.length - 1] = {
                ...lastMsg,
                loading: { ...lastMsg.loading, stage3: true },
              };
              return { ...prev, messages };
            });
            break;

          case 'stage3_complete':
            // Mark stage 3 as completed (updates ref synchronously to prevent timer race condition)
            markStageCompleted('stage3');
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              messages[messages.length - 1] = {
                ...lastMsg,
                stage3: event.data,
                loading: { ...lastMsg.loading, stage3: false },
              };
              return { ...prev, messages };
            });
            break;

          case 'title_complete':
            // Reload conversations to get updated title
            loadConversations();
            break;

          case 'complete':
            // Stream complete, reload conversations list
            loadConversations();
            setIsLoading(false);
            break;

          case 'error':
            console.error('Stream error:', event.message);
            setIsLoading(false);
            break;

          default:
            console.log('Unknown event type:', eventType);
        }
      }, originalQuery);
    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove optimistic messages on error
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        userMenu={<UserMenu />}
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        stageTimings={stageTimings}
        modelStatuses={modelStatuses}
        modelTimings={modelTimings}
      />
    </div>
  );
}

export default App;
