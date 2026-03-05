import { useState, useEffect } from 'react';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  selectedProvider,
  onProviderChange,
}) {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        
        <div className="provider-selector">
          <label>Model Provider:</label>
          <div className="provider-radios">
            <label>
              <input
                type="radio"
                name="provider"
                value="openai"
                checked={selectedProvider === 'openai'}
                onChange={(e) => onProviderChange(e.target.value)}
              />
              OpenAI
            </label>
            <label>
              <input
                type="radio"
                name="provider"
                value="gemini"
                checked={selectedProvider === 'gemini'}
                onChange={(e) => onProviderChange(e.target.value)}
              />
              Gemini
            </label>
            <label>
              <input
                type="radio"
                name="provider"
                value="claude"
                checked={selectedProvider === 'claude'}
                onChange={(e) => onProviderChange(e.target.value)}
              />
              Claude
            </label>
            <label>
              <input
                type="radio"
                name="provider"
                value="cerebras"
                checked={selectedProvider === 'cerebras'}
                onChange={(e) => onProviderChange(e.target.value)}
              />
              Cerebras
            </label>
          </div>
        </div>

        <button className="new-conversation-btn" onClick={onNewConversation}>
          + New Conversation
        </button>
      </div>

      <div className="conversation-list">
        {conversations.length === 0 ? (
          <div className="no-conversations">No conversations yet</div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${
                conv.id === currentConversationId ? 'active' : ''
              }`}
              onClick={() => onSelectConversation(conv.id)}
            >
              <div className="conversation-title">
                {conv.title || 'New Conversation'}
              </div>
              <div className="conversation-meta">
                {conv.message_count} messages
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
