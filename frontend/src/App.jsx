import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useParams, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { ThemeProvider } from './contexts/ThemeContext';
import { api } from './api';
import './App.css';

function ConversationView() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const [conversations, setConversations] = useState([]);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showCost, setShowCost] = useState(() => {
    const saved = localStorage.getItem('showCost');
    return saved !== 'false';
  });
  const pollIntervalsRef = useRef({});

  // Helper functions for pendingJobs management
  const addPendingJob = useCallback((jobId, convId) => {
    if (!jobId || !convId) return;
    const pendingJobs = JSON.parse(localStorage.getItem('pendingJobs') || '{}');
    pendingJobs[jobId] = convId;
    localStorage.setItem('pendingJobs', JSON.stringify(pendingJobs));
  }, []);

  const removePendingJob = useCallback((jobId) => {
    if (!jobId) return;
    const pendingJobs = JSON.parse(localStorage.getItem('pendingJobs') || '{}');
    delete pendingJobs[jobId];
    if (Object.keys(pendingJobs).length === 0) {
      localStorage.removeItem('pendingJobs');
    } else {
      localStorage.setItem('pendingJobs', JSON.stringify(pendingJobs));
    }
  }, []);

  const loadConversations = useCallback(async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  }, []);

  const loadConversation = useCallback(async (id) => {
    try {
      const conv = await api.getConversation(id);
      
      // Check for pending jobs and mark messages accordingly
      const pendingJobs = JSON.parse(localStorage.getItem('pendingJobs') || '{}');
      const jobsForConv = Object.entries(pendingJobs).filter(([, convId]) => convId === id);
      
      if (jobsForConv.length > 0) {
        const jobId = jobsForConv[0][0];
        
        // Find last assistant message without stage3
        const lastAssistantIndex = conv.messages.map((m, i) => ({ msg: m, idx: i }))
          .filter(({ msg }) => msg.role === 'assistant' && !msg.stage3)
          .pop()?.idx;
        
        if (lastAssistantIndex !== undefined) {
          // Update existing incomplete assistant message
          conv.messages[lastAssistantIndex] = {
            ...conv.messages[lastAssistantIndex],
            jobId: jobId,
            jobStatus: 'processing'
          };
        } else {
          // No incomplete assistant message - add one for the pending job
          conv.messages.push({
            role: 'assistant',
            stage1: null,
            stage2: null,
            stage3: null,
            metadata: null,
            jobId: jobId,
            jobStatus: 'processing'
          });
        }
      }
      
      setCurrentConversation(conv);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  }, []);

  const pollJobStatus = useCallback((jobId, convId) => {
    // Clear existing interval if any
    if (pollIntervalsRef.current[jobId]) {
      clearInterval(pollIntervalsRef.current[jobId]);
    }
    
    const pollInterval = setInterval(async () => {
      try {
        const job = await api.getJobStatus(jobId);
        
        if (job.status === 'completed') {
          clearInterval(pollInterval);
          delete pollIntervalsRef.current[jobId];
          removePendingJob(jobId);
          
          // Reload conversation to show result
          if (convId) {
            await loadConversation(convId);
          }
          setIsLoading(false);
          loadConversations();
        } else if (job.status === 'failed') {
          clearInterval(pollInterval);
          delete pollIntervalsRef.current[jobId];
          removePendingJob(jobId);
          
          // Only show error if not cancelled by user
          if (job.error !== 'Cancelled by user') {
            console.error('Job failed:', job.error);
          }
          
          // Reload conversation to update UI
          if (convId) {
            await loadConversation(convId);
          }
          
          setIsLoading(false);
        } else {
          // Still processing - update UI only if we're still on the same conversation
          if (convId) {
            setCurrentConversation((prev) => {
              // Don't update if we've navigated to a different conversation
              if (!prev || prev.id !== convId) return prev;
              
              const messages = [...prev.messages];
              const msgIndex = messages.findIndex(m => m.role === 'assistant' && m.jobId === jobId);
              if (msgIndex !== -1) {
                messages[msgIndex] = { ...messages[msgIndex], jobStatus: job.status };
                return { ...prev, messages };
              }
              // Don't add new message if not found - it means we're on wrong conversation
              return prev;
            });
          }
        }
      } catch (error) {
        console.error('Failed to poll job status:', error);
      }
    }, 3000);
    
    pollIntervalsRef.current[jobId] = pollInterval;
  }, [loadConversation, loadConversations, removePendingJob]);

  // Cleanup invalid pending jobs and load conversations on mount
  useEffect(() => {
    const pendingJobs = JSON.parse(localStorage.getItem('pendingJobs') || '{}');
    const cleaned = {};
    Object.entries(pendingJobs).forEach(([key, value]) => {
      if (key && typeof key === 'string' && key.length > 10 && value) {
        cleaned[key] = value;
      }
    });
    if (Object.keys(cleaned).length === 0) {
      localStorage.removeItem('pendingJobs');
    } else {
      localStorage.setItem('pendingJobs', JSON.stringify(cleaned));
    }
    loadConversations();
  }, [loadConversations]);

  // Load conversation details when URL changes
  useEffect(() => {
    // Always reset current conversation first when changing
    setCurrentConversation(null);
    
    if (conversationId) {
      // Check for pending jobs and load conversation
      const pendingJobs = JSON.parse(localStorage.getItem('pendingJobs') || '{}');
      const jobsForConv = Object.entries(pendingJobs).filter(([, convId]) => convId === conversationId);
      
      if (jobsForConv.length > 0) {
        // Set placeholder for immediate feedback
        setCurrentConversation({
          id: conversationId,
          messages: [{
            role: 'user',
            content: 'Loading previous message...'
          }, {
            role: 'assistant',
            stage1: null,
            stage2: null,
            stage3: null,
            metadata: null,
            jobStatus: 'processing',
            jobId: jobsForConv[0][0]
          }],
          created_at: new Date().toISOString(),
          title: 'Loading...'
        });
        
        // Load actual conversation in background
        setTimeout(() => loadConversation(conversationId), 0);
      } else {
        loadConversation(conversationId);
      }
    }
  }, [conversationId, loadConversation]);

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([
        { id: newConv.id, created_at: newConv.created_at, message_count: 0 },
        ...conversations,
      ]);
      navigate(`/c/${newConv.id}`); // Navigate to new conversation URL
      setSidebarOpen(false); // Close sidebar on mobile after creating new conversation
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = (id) => {
    navigate(`/c/${id}`); // Navigate to conversation URL
    setSidebarOpen(false); // Close sidebar on mobile after selecting
  };

  const handleDeleteConversation = async (convId) => {
    if (!confirm('Are you sure you want to delete this conversation?')) {
      return;
    }
    
    try {
      await api.deleteConversation(convId);
      
      // Remove from conversations list
      setConversations(conversations.filter(c => c.id !== convId));
      
      // If current conversation was deleted, navigate to home
      if (conversationId === convId) {
        navigate('/');
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      alert('Failed to delete conversation');
    }
  };

  // Check for pending jobs on mount and resume polling
  useEffect(() => {
    if (!conversationId) return;
    
    const pendingJobs = JSON.parse(localStorage.getItem('pendingJobs') || '{}');
    const jobsForConv = Object.entries(pendingJobs).filter(([, convId]) => convId === conversationId);
    
    if (jobsForConv.length > 0) {
      jobsForConv.forEach(([jobId, convId]) => {
        pollJobStatus(jobId, convId);
      });
    }
  }, [conversationId, pollJobStatus]);

  const handleSendMessage = async (content) => {
    if (!conversationId) return;

    // Don't set isLoading - we'll show job status in message instead
    // setIsLoading(true);
    
    try {
      // Optimistically add user message AND placeholder assistant message together
      // This prevents the flash of "retry" button
      const userMessage = { role: 'user', content };
      const placeholderAssistant = {
        role: 'assistant',
        stage1: null,
        stage2: null,
        stage3: null,
        metadata: null,
        jobStatus: 'pending',
        jobId: 'pending', // Temporary placeholder
      };
      
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage, placeholderAssistant],
      }));

      // Send message for async processing
      const response = await api.sendMessageAsync(conversationId, content);
      const { job_id, title } = response || {};
      
      // Validate job_id
      if (!job_id) {
        console.error('No job_id returned from API');
        throw new Error('Failed to queue message');
      }
      
      // Update title if returned (first message)
      if (title) {
        setCurrentConversation((prev) => ({ ...prev, title }));
        // Also update conversations list
        setConversations((prev) => 
          prev.map(c => c.id === conversationId ? { ...c, title } : c)
        );
      }
      
      // Update placeholder with real job_id
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.map((msg, idx) => 
          idx === prev.messages.length - 1 && msg.jobId === 'pending'
            ? { ...msg, jobId: job_id }
            : msg
        ),
      }));
      
      // Store job_id in localStorage for recovery after browser close
      addPendingJob(job_id, conversationId);
      
      // Start polling for job status
      pollJobStatus(job_id, conversationId);

    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove optimistic messages on error
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      // setIsLoading(false); // Not needed anymore
    }
  };

  const handleCancelJob = async (jobId) => {
    if (!jobId) {
      console.error('No jobId provided for cancel');
      return;
    }
    
    try {
      await api.cancelJob(jobId);
      removePendingJob(jobId);
      
      // Reload conversation
      if (conversationId) {
        await loadConversation(conversationId);
      }
    } catch (error) {
      console.error('Failed to cancel job:', error);
      alert('Failed to cancel job');
    }
  };

  const handleRetry = async () => {
    if (!conversationId) return;
    
    try {
      const response = await api.retryLastMessage(conversationId);
      const { job_id } = response || {};
      
      // Validate job_id
      if (!job_id) {
        console.error('No job_id returned from retry API');
        throw new Error('Failed to retry message');
      }
      
      // Store job_id in localStorage
      addPendingJob(job_id, conversationId);
      
      // Reload conversation and start polling
      await loadConversation(conversationId);
      pollJobStatus(job_id, conversationId);
    } catch (error) {
      console.error('Failed to retry:', error);
      alert('Failed to retry message');
    }
  };

  return (
    <ThemeProvider>
      <div className="app">
        {/* Hamburger menu button - mobile only */}
        <button 
          className={`hamburger-menu ${sidebarOpen ? 'open' : ''}`}
          onClick={() => setSidebarOpen(!sidebarOpen)}
          aria-label="Toggle menu"
        >
          <span></span>
          <span></span>
          <span></span>
        </button>

        <Sidebar
          conversations={conversations}
          currentConversationId={conversationId}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
          onDeleteConversation={handleDeleteConversation}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          showCost={showCost}
          onSettingsChange={(settings) => {
            if (settings.showCost !== undefined) {
              setShowCost(settings.showCost);
            }
          }}
        />
        <ChatInterface
          conversation={currentConversation}
          conversationId={conversationId}
          onSendMessage={handleSendMessage}
          onCancelJob={handleCancelJob}
          onRetry={handleRetry}
          isLoading={isLoading}
          showCost={showCost}
        />
      </div>
    </ThemeProvider>
  );
}

function App() {
  return (
    <ThemeProvider>
      <Routes>
        <Route path="/" element={<ConversationView />} />
        <Route path="/c/:conversationId" element={<ConversationView />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ThemeProvider>
  );
}

export default App;
