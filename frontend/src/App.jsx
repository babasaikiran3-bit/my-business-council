import { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import ConsensusPreview from './components/ConsensusPreview';
import { api } from './api';
import { councilReducer, createAssistantMessage } from './reducers/councilReducer';
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

  const loadConversations = useCallback(async () => {
    try {
      setConversations(await api.listConversations());
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  }, []);

  useEffect(() => { loadConversations(); }, [loadConversations]);

  const setRepo = useCallback((path) => {
    setCurrentRepo(path);
    localStorage.setItem('councilRepo', path || '');
  }, []);

  const loadConversation = useCallback(async (id) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
      // El repo queda atado a la conversación: al abrirla, se autoselecciona.
      if (conv.repo_path) setRepo(conv.repo_path);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  }, [setRepo]);

  useEffect(() => {
    if (currentConversationId) loadConversation(currentConversationId);
  }, [currentConversationId, loadConversation]);

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

  /** Apply a council reducer action to the last (assistant) message. */
  const dispatchToLast = (action) => {
    setCurrentConversation((prev) => {
      const messages = [...prev.messages];
      const last = councilReducer({ ...messages[messages.length - 1] }, action);
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
          createAssistantMessage(),
        ],
      }));

      await api.streamMessage(
        { conversationId: currentConversationId, content, repoPath: currentRepo,
          research: opts.research !== false },
        (event) => {
          switch (event.type) {
            case 'stage':
              dispatchToLast({ type: 'STAGE', stage: event.stage });
              break;
            case 'agent':
              dispatchToLast({ type: 'AGENT', model: event.model, status: event.status, reason: event.reason });
              break;
            case 'tool':
              dispatchToLast({ type: 'TOOL', model: event.model, tool: event.tool, detail: event.detail });
              break;
            case 'thought':
              dispatchToLast({ type: 'THOUGHT', model: event.model, text: event.text });
              break;
            case 'result':
              dispatchToLast({ type: 'RESULT', model: event.model, text: event.text });
              break;
            case 'research':
              dispatchToLast({ type: 'RESEARCH', model: event.model, brief: event.brief });
              break;
            case 'ranking':
              dispatchToLast({ type: 'RANKING', aggregate: event.aggregate });
              break;
            case 'metadata':
              dispatchToLast({ type: 'METADATA', metadata: event.metadata });
              break;
            case 'consensus_file':
              dispatchToLast({ type: 'CONSENSUS_FILE', path: event.path });
              break;
            case 'final':
              dispatchToLast({ type: 'FINAL', model: event.model, text: event.text });
              break;
            case 'title':
              loadConversations();
              break;
            case 'done':
              dispatchToLast({
                type: 'DONE',
                stage1: event.stage1,
                stage2: event.stage2,
                stage3: event.stage3,
                metadata: event.metadata,
              });
              loadConversations();
              setIsLoading(false);
              break;
            case 'fatal':
              console.error('Stream fatal:', event.message);
              dispatchToLast({ type: 'FATAL', message: event.message });
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
      dispatchToLast({ type: 'ERROR', message: `No se pudo generar el documento: ${error.message}` });
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
      dispatchToLast({ type: 'CONSENSUS_FILE', path: res.consensus_file });
      setPreviewDoc(null);
    } catch (error) {
      console.error('Failed to approve consensus:', error);
      dispatchToLast({ type: 'ERROR', message: `No se pudo escribir: ${error.message}` });
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
