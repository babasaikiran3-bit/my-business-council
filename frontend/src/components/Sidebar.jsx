import { useState, useEffect } from 'react';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  onDeleteAllConversations,
}) {
  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>Council of Sheldons</h1>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          + New Conversation
        </button>
      </div>

      <div className="conversation-list">
        {conversations.length > 0 && (
          <div className="conversation-list-header">
            <button
              className="delete-all-btn"
              onClick={onDeleteAllConversations}
              title="Delete all conversations"
            >
              Delete All
            </button>
          </div>
        )}
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
              <div className="conversation-content">
                <div className="conversation-title">
                  {conv.title || 'New Conversation'}
                </div>
                <div className="conversation-meta">
                  {conv.message_count} messages
                </div>
              </div>
              <button
                className="delete-conversation-btn"
                onClick={(e) => onDeleteConversation(conv.id, e)}
                title="Delete conversation"
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
