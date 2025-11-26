import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { api } from './api';
import './App.css';

const LAST_CONVERSATION_KEY = 'llm-council:last-conversation';

const getStoredConversationId = () => {
  if (typeof window === 'undefined') {
    return null;
  }
  return window.localStorage.getItem(LAST_CONVERSATION_KEY);
};

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(
    () => getStoredConversationId() || null
  );
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isConnecting, setIsConnecting] = useState(true);

  // Load conversations on mount
  useEffect(() => {
    const init = async () => {
      const success = await loadConversations();
      if (success) {
        setIsConnecting(false);
        return;
      }

      // Retry if backend is not ready yet
      const interval = setInterval(async () => {
        const retrySuccess = await loadConversations();
        if (retrySuccess) {
          clearInterval(interval);
          setIsConnecting(false);
        }
      }, 500);

      // Stop retrying after 10 seconds
      setTimeout(() => {
        clearInterval(interval);
        setIsConnecting(false);
      }, 10000);
    };
    init();
  }, []);

  // Persist the current conversation selection
  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }
    if (currentConversationId) {
      window.localStorage.setItem(LAST_CONVERSATION_KEY, currentConversationId);
    } else {
      window.localStorage.removeItem(LAST_CONVERSATION_KEY);
    }
  }, [currentConversationId]);

  // Load conversation details when selected
  useEffect(() => {
    if (currentConversationId) {
      loadConversation(currentConversationId);
    }
  }, [currentConversationId]);

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
      if (convs.length === 0) {
        setCurrentConversationId(null);
        setCurrentConversation(null);
        return true;
      }

      setCurrentConversationId((prevId) => {
        if (prevId && convs.some((conv) => conv.id === prevId)) {
          return prevId;
        }

        const storedId = getStoredConversationId();
        if (storedId && convs.some((conv) => conv.id === storedId)) {
          return storedId;
        }

        return convs[0].id;
      });

      return true;
    } catch (error) {
      console.error('Failed to load conversations:', error);
      return false;
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
    if (isCreating) return;
    setIsCreating(true);
    try {
      const newConv = await api.createConversation();
      setConversations(prev => [
        { id: newConv.id, created_at: newConv.created_at, message_count: 0 },
        ...prev,
      ]);
      setCurrentConversationId(newConv.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
      alert('Failed to create conversation. Please check if the backend is running.');
    } finally {
      setIsCreating(false);
    }
  };

  const handleSelectConversation = (id) => {
    if (id !== currentConversationId) {
      setCurrentConversation(null);
      setCurrentConversationId(id);
    }
  };

  const handleDeleteConversation = async (conversationId) => {
    if (typeof window !== 'undefined') {
      const confirmed = window.confirm('Delete this conversation?');
      if (!confirmed) {
        return;
      }
    }

    try {
      await api.deleteConversation(conversationId);
      setConversations((prevConvs) => {
        const updated = prevConvs.filter((conv) => conv.id !== conversationId);

        setCurrentConversationId((prevId) => {
          if (prevId === conversationId) {
            return updated[0]?.id || null;
          }
          return prevId;
        });

        if (currentConversation?.id === conversationId) {
          setCurrentConversation(null);
        }

        return updated;
      });
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      alert('Failed to delete conversation. Please try again.');
    }
  };

  const handleSendMessage = async (content) => {
    if (!currentConversationId) return;

    setIsLoading(true);
    try {
      // Optimistically add user message to UI
      const userMessage = { role: 'user', content };
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }));

      // Create a partial assistant message that will be updated progressively
      const assistantMessage = {
        role: 'assistant',
        stage1: null,
        stage2: null,
        stage3: null,
        metadata: null,
        loading: {
          stage1: false,
          stage2: false,
          stage3: false,
        },
      };

      // Add the partial assistant message
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      // Send message with streaming
      await api.sendMessageStream(currentConversationId, content, (eventType, event) => {
        switch (eventType) {
          case 'stage1_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage1 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage1_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage1 = event.data;
              lastMsg.loading.stage1 = false;
              return { ...prev, messages };
            });
            break;

          case 'stage2_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage2 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage2_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage2 = event.data;
              lastMsg.metadata = event.metadata;
              lastMsg.loading.stage2 = false;
              return { ...prev, messages };
            });
            break;

          case 'stage3_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage3 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage3_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage3 = event.data;
              lastMsg.loading.stage3 = false;
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
      });
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
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
      onNewConversation={handleNewConversation}
      onDeleteConversation={handleDeleteConversation}
      isCreating={isCreating}
      isConnecting={isConnecting}
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
      />
    </div>
  );
}

export default App;
