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
  const [deletingIds, setDeletingIds] = useState(new Set());

  const handleDeleteClick = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this conversation?')) {
      return;
    }

    // Start deletion animation
    setDeletingIds(prev => new Set(prev).add(id));

    // Wait for animation to complete, then delete
    setTimeout(async () => {
      await onDeleteConversation(id, e);
      setDeletingIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }, 300); // Match CSS animation duration
  };

  const handleDeleteAllClick = async () => {
    if (!window.confirm('Are you sure you want to delete ALL conversations? This cannot be undone.')) {
      return;
    }

    // Start deletion animation for all items
    const allIds = new Set(conversations.map(conv => conv.id));
    setDeletingIds(allIds);

    // Wait for animation, then delete all
    setTimeout(async () => {
      await onDeleteAllConversations();
      setDeletingIds(new Set());
    }, 300);
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          + New Conversation
        </button>
        {conversations.length > 0 && (
          <button 
            className="delete-all-btn" 
            onClick={handleDeleteAllClick}
            title="Delete all conversations"
          >
            Delete All
          </button>
        )}
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
              } ${deletingIds.has(conv.id) ? 'deleting' : ''}`}
              onClick={() => !deletingIds.has(conv.id) && onSelectConversation(conv.id)}
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
                className="delete-btn"
                onClick={(e) => handleDeleteClick(conv.id, e)}
                title="Delete conversation"
                disabled={deletingIds.has(conv.id)}
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
