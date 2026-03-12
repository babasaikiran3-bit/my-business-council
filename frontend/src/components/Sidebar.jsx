import { useState, useEffect } from 'react';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onNewTemporaryConversation,
  onDeleteConversation,
}) {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <div className="sidebar-actions">
          <button className="new-conversation-btn" onClick={onNewConversation}>
            + New Conversation
          </button>
          <button className="new-temp-btn" onClick={onNewTemporaryConversation} title="Conversation won't be saved to disk">
            + Temporary Chat
          </button>
        </div>
      </div>

      <div className="conversation-list">
        {conversations.length === 0 ? (
          <div className="no-conversations">No conversation history</div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${
                conv.id === currentConversationId ? 'active' : ''
              }`}
              onClick={() => onSelectConversation(conv.id)}
            >
              <div className="conversation-content">
                <div className="conversation-title">
                  {conv.title || 'New Conversation'}
                  {conv.is_temporary && <span className="temp-badge">Incognito</span>}
                </div>
                <div className="conversation-meta">
                  {conv.message_count} Messages
                </div>
              </div>
              <button 
                className="delete-btn" 
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteConversation(conv.id);
                }}
                title="Delete Chat"
              >
                ×
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
