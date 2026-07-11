import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import ConsensusPreview from './components/ConsensusPreview';
import { api } from './api';
import './App.css';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isDocumenting, setIsDocumenting] = useState(false);
  const [previewDoc, setPreviewDoc] = useState(null);
  const [isApproving, setIsApproving] = useState(false);
  const [currentRepo, setCurrentRepo] = useState(
    () => localStorage.getItem('councilRepo') || ''
  );

  useEffect(() => { loadConversations(); }, []);

  useEffect(() => {
    if (currentConversationId) loadConversation(currentConversationId);
  }, [currentConversationId]);

  const setRepo = (path) => {
    setCurrentRepo(path);
    localStorage.setItem('councilRepo', path || '');
  };

  const loadConversations = async () => {
    try {
      setConversations(await api.listConversations());
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
      // El repo queda atado a la conversación: al abrirla, se autoselecciona.
      if (conv.repo_path) setRepo(conv.repo_path);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([
        { id: newConv.id, created_at: newConv.created_at, title: newConv.title, message_count: 0 },
        ...conversations,
      ]);
      setCurrentConversationId(newConv.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = (id) => setCurrentConversationId(id);

  const handleDeleteConversation = async (id) => {
    try {
      await api.deleteConversation(id);
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (id === currentConversationId) {
        setCurrentConversationId(null);
        setCurrentConversation(null);
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  // Helper: muta el último mensaje (asistente) del estado
  const updateLast = (mutator) => {
    setCurrentConversation((prev) => {
      const messages = [...prev.messages];
      const last = { ...messages[messages.length - 1] };
      mutator(last);
      messages[messages.length - 1] = last;
      return { ...prev, messages };
    });
  };

  const handleSendMessage = async (content, opts = {}) => {
    if (!currentConversationId) return;
    setIsLoading(true);
    try {
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [
          ...prev.messages,
          { role: 'user', content },
          { role: 'assistant', live: {}, stage: null, stage1: null, stage2: null, stage3: null, metadata: null, research: null },
        ],
      }));

      await api.streamMessage(
        { conversationId: currentConversationId, content, repoPath: currentRepo,
          research: opts.research !== false },
        (event) => {
          switch (event.type) {
            case 'stage':
              updateLast((m) => { m.stage = event.stage; });
              break;
            case 'agent':
              updateLast((m) => {
                m.live = { ...m.live, [event.model]: { ...(m.live[event.model] || {}), status: event.status, reason: event.reason } };
              });
              break;
            case 'tool':
              updateLast((m) => {
                m.live = { ...m.live, [event.model]: { status: 'working', tool: event.tool, detail: event.detail } };
              });
              break;
            case 'thought':
              updateLast((m) => {
                m.live = { ...m.live, [event.model]: { status: 'working', thought: event.text } };
              });
              break;
            case 'result':
              updateLast((m) => {
                const existing = m.stage1 || [];
                m.stage1 = [...existing.filter((r) => r.model !== event.model), { model: event.model, response: event.text }];
              });
              break;
            case 'research':
              updateLast((m) => {
                m.research = { model: event.model, brief: event.brief };
                m.live = {}; // limpiar el progreso del investigador antes de Stage 1
              });
              break;
            case 'ranking':
              updateLast((m) => { m.metadata = { ...(m.metadata || {}), aggregate_rankings: event.aggregate }; });
              break;
            case 'metadata':
              updateLast((m) => { m.metadata = { ...(m.metadata || {}), ...event.metadata }; });
              break;
            case 'consensus_file':
              updateLast((m) => { m.consensusFile = event.path; });
              break;
            case 'final':
              updateLast((m) => { m.stage3 = { model: event.model, response: event.text }; });
              break;
            case 'title':
              loadConversations();
              break;
            case 'done':
              updateLast((m) => {
                m.stage1 = event.stage1;
                m.stage2 = event.stage2;
                m.stage3 = event.stage3;
                m.metadata = event.metadata;
                if (event.metadata?.research) m.research = event.metadata.research;
                m.stage = null;
                m.live = {};
              });
              loadConversations();
              setIsLoading(false);
              break;
            case 'fatal':
              console.error('Stream fatal:', event.message);
              updateLast((m) => { m.error = event.message; m.stage = null; });
              setIsLoading(false);
              break;
            default:
              console.log('Unknown event:', event);
          }
        }
      );
    } catch (error) {
      console.error('Failed to send message:', error);
      setCurrentConversation((prev) => ({ ...prev, messages: prev.messages.slice(0, -2) }));
      setIsLoading(false);
    }
  };

  // Paso 1: genera el documento (sin escribir) y abre la previsualización.
  const handleDocumentConsensus = async () => {
    if (!currentConversationId || !currentRepo) return;
    setIsDocumenting(true);
    try {
      const preview = await api.previewConsensus(currentConversationId, currentRepo);
      setPreviewDoc(preview);
    } catch (error) {
      console.error('Failed to preview consensus:', error);
      updateLast((m) => { m.error = `No se pudo generar el documento: ${error.message}`; });
    } finally {
      setIsDocumenting(false);
    }
  };

  // Paso 2a: aprobar → el backend escribe el archivo en el repo.
  const handleApproveConsensus = async () => {
    if (!currentConversationId) return;
    setIsApproving(true);
    try {
      const res = await api.approveConsensus(currentConversationId, currentRepo);
      updateLast((m) => { m.consensusFile = res.consensus_file; });
      setPreviewDoc(null);
    } catch (error) {
      console.error('Failed to approve consensus:', error);
      updateLast((m) => { m.error = `No se pudo escribir: ${error.message}`; });
    } finally {
      setIsApproving(false);
    }
  };

  // Paso 2b: descartar → tira el borrador, no escribe nada.
  const handleDiscardConsensus = async () => {
    setPreviewDoc(null);
    if (currentConversationId) {
      try { await api.discardConsensus(currentConversationId); } catch { /* noop */ }
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
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        currentRepo={currentRepo}
        onRepoChange={setRepo}
        onDocumentConsensus={handleDocumentConsensus}
        isDocumenting={isDocumenting}
      />
      <ConsensusPreview
        preview={previewDoc}
        repoPath={currentRepo}
        busy={isApproving}
        onApprove={handleApproveConsensus}
        onDiscard={handleDiscardConsensus}
      />
    </div>
  );
}

export default App;
