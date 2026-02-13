import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage3 from './Stage3';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  onUploadFile,
  onDeleteFile,
}) {
  const [input, setInput] = useState('');
  const [uploadStatus, setUploadStatus] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation?.messages]); // Scroll when messages change

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim()) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadStatus('Uploading...');
    try {
      const result = await onUploadFile(file);
      setUploadStatus('');
      setUploadedFiles(prev => [...prev, { name: result.filename, id: Date.now() }]);
    } catch (error) {
      setUploadStatus(`Error: ${error.message}`);
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleRemoveFile = async (filename) => {
    try {
      await onDeleteFile(filename);
      setUploadedFiles(prev => prev.filter(f => f.name !== filename));
    } catch (error) {
      console.error("Failed to remove file:", error);
      setUploadStatus(`Error removing file: ${error.message}`);
    }
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <h2>Welcome to LLM Council</h2>
          <p>Create a new conversation to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a conversation</h2>
            <p>Ask a question to consult the LLM Council</p>
          </div>
        ) : (
          conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-content">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  {/* Stage 1 */}
                  {msg.loading?.stage1 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Collecting individual responses...</span>
                    </div>
                  )}
                  {msg.stage1 && <Stage1 responses={msg.stage1} />}

                  {/* Stage 3 */}
                  {msg.loading?.stage3 && !msg.stage3?.response && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Synthesizing final answer...</span>
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

      <div className="input-form">
        <div className="input-container">
          {uploadedFiles.length > 0 && (
            <div className="file-list">
              {uploadedFiles.map(file => (
                <div key={file.id} className="file-chip">
                  <span>📄</span>
                  <span>{file.name}</span>
                  <button
                    type="button"
                    className="remove-file-btn"
                    onClick={() => handleRemoveFile(file.name)}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          <div className="input-row">
            <button
              type="button"
              className="upload-button"
              onClick={() => fileInputRef.current?.click()}
              title="Upload document"
            >
              📎
            </button>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              style={{ display: 'none' }}
              accept=".pdf,.txt,.md"
            />

            <textarea
              className="message-input"
              placeholder="Ask the council..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
            />

            <button
              type="button"
              className="send-button"
              onClick={handleSubmit}
              disabled={!input.trim()}
            >
              Send
            </button>
          </div>
          {uploadStatus && <div className="upload-status">{uploadStatus}</div>}
        </div>
      </div>
    </div>
  );
}
