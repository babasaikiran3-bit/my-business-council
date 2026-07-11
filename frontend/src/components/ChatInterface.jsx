import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import RepoSelector from './RepoSelector';
import CouncilConfig from './CouncilConfig';
import LiveProgress from './LiveProgress';
import './ChatInterface.css';

const STAGE_LABEL = { 0: 'investigando (web)', 1: 'explorando repo', 2: 'ranking', 3: 'síntesis' };

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  currentRepo,
  onRepoChange,
  onDocumentConsensus,
  isDocumenting,
}) {
  const [input, setInput] = useState('');
  const [writeConsensus, setWriteConsensus] = useState(false);
  const [research, setResearch] = useState(true); // Ronda 0 de búsqueda, ON por defecto
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => { scrollToBottom(); }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input, { research });
      setInput('');
    }
  };

  // ¿Hay un consenso (Stage 3) en el último turno, listo para documentar?
  const lastMsg = conversation?.messages?.[conversation.messages.length - 1];
  const hasConsensus = !!(lastMsg && lastMsg.role === 'assistant' && lastMsg.stage3);
  const alreadyDocumented = !!(lastMsg && (lastMsg.consensusFile || lastMsg.stage3?.consensus_file));
  const canDocument =
    writeConsensus && !!currentRepo && hasConsensus && !alreadyDocumented && !isLoading && !isDocumenting;

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <h2>Welcome to LLM Council</h2>
          <p>Creá una conversación para empezar</p>
        </div>
      </div>
    );
  }

  const header = (
    <div className="chat-header">
      <RepoSelector value={currentRepo} onChange={onRepoChange} />
      <CouncilConfig />
    </div>
  );

  return (
    <div className="chat-interface">
      {header}
      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Empezá una consulta</h2>
            <p>{currentRepo ? `El consejo debatirá sobre ${currentRepo}` : 'Preguntale al consejo (sin repo: Q&A general)'}</p>
          </div>
        ) : (
          conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-label">You</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="message-label">LLM Council</div>

                  {/* Progreso en vivo (mientras corre, antes de la síntesis) */}
                  {msg.live && Object.keys(msg.live).length > 0 && !msg.stage3 && (
                    <LiveProgress agents={msg.live} stageLabel={STAGE_LABEL[msg.stage]} />
                  )}

                  {msg.error && <div className="stage-error">⚠ {msg.error}</div>}

                  {/* Stage 0 — brief de investigación (colapsable) */}
                  {(msg.research?.brief || msg.metadata?.research?.brief) && (
                    <details className="research-brief">
                      <summary>
                        🔎 Ronda 0 · Investigación
                        <span className="research-by"> — {msg.research?.model || msg.metadata?.research?.model}</span>
                      </summary>
                      <div className="markdown-content">
                        <ReactMarkdown>{msg.research?.brief || msg.metadata?.research?.brief}</ReactMarkdown>
                      </div>
                    </details>
                  )}

                  {/* Stage 1 */}
                  {msg.stage1 && msg.stage1.length > 0 && <Stage1 responses={msg.stage1} />}

                  {/* Stage 2 */}
                  {msg.stage === 2 && !msg.stage2 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Etapa 2: ranking ciego entre pares…</span>
                    </div>
                  )}
                  {msg.stage2 && (
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                    />
                  )}

                  {/* Stage 3 */}
                  {msg.stage === 3 && !msg.stage3 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Etapa 3: síntesis del chairman…</span>
                    </div>
                  )}
                  {(msg.consensusFile || msg.stage3?.consensus_file) && (
                    <div className="consensus-file">
                      📝 Consenso documentado en el repo:{' '}
                      <code>{msg.consensusFile || msg.stage3.consensus_file}</code>
                    </div>
                  )}
                  {msg.stage3 && <Stage3 finalResponse={msg.stage3} />}
                </div>
              )}
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <form className="input-form" onSubmit={handleSubmit}>
        <div className="input-col">
          <textarea
            className="message-input"
            placeholder={
              conversation.messages.length === 0
                ? 'Tu pregunta… (Shift+Enter nueva línea, Enter envía)'
                : 'Seguí la conversación… (el consejo recuerda los turnos previos)'
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={3}
          />
          <div className="input-actions">
            <div className="toggles">
            <label
              className="write-toggle"
              title="Ronda 0: antes de deliberar, el investigador busca info actual en la web y se la pasa a todo el consejo"
            >
              <input
                type="checkbox"
                checked={research}
                onChange={(e) => setResearch(e.target.checked)}
              />
              🔎 Ronda de búsqueda previa
            </label>
            <label
              className={`write-toggle ${!currentRepo ? 'disabled' : ''}`}
              title={currentRepo
                ? 'Habilita el botón para que el chairman escriba el consenso en docs/council/ del repo'
                : 'Seleccioná un repo para habilitar la escritura'}
            >
              <input
                type="checkbox"
                checked={writeConsensus && !!currentRepo}
                disabled={!currentRepo}
                onChange={(e) => setWriteConsensus(e.target.checked)}
              />
              ✍️ Permitir documentar el consenso en el repo
            </label>
            </div>
            <button
              type="button"
              className="document-button"
              disabled={!canDocument}
              onClick={() => onDocumentConsensus()}
              title={
                !writeConsensus ? 'Marcá la casilla para habilitar'
                  : !currentRepo ? 'Seleccioná un repo'
                  : !hasConsensus ? 'Primero el consejo tiene que llegar a un consenso'
                  : alreadyDocumented ? 'Este consenso ya fue documentado'
                  : `El chairman escribirá el consenso en ${currentRepo}/docs/council/`
              }
            >
              {isDocumenting ? '📝 Generando…' : '📝 Documentar lo decidido'}
            </button>
          </div>
        </div>
        <button type="submit" className="send-button" disabled={!input.trim() || isLoading}>
          {isLoading ? 'Deliberando…' : 'Enviar'}
        </button>
      </form>
    </div>
  );
}
