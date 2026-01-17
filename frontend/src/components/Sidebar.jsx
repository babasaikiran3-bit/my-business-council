import { useState } from 'react';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  archivedConversations = [],
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onArchiveConversation,
  onUnarchiveConversation,
  onDeleteConversation,
  showArchived = false,
  onToggleShowArchived,
  onOpenSearch,
}) {
  const [confirmDelete, setConfirmDelete] = useState(null); // conversation id to confirm delete

  const handleConversationClick = (e, id) => {
    // Allow cmd+click (Mac) or ctrl+click (Windows) to open in new tab
    if (e.metaKey || e.ctrlKey) {
      // Let the default anchor behavior handle it
      return;
    }
    e.preventDefault();
    onSelectConversation(id);
  };

  const handleArchive = (e, id) => {
    e.preventDefault();
    e.stopPropagation();
    onArchiveConversation(id);
  };

  const handleUnarchive = (e, id) => {
    e.preventDefault();
    e.stopPropagation();
    onUnarchiveConversation(id);
  };

  const handleDeleteClick = (e, id) => {
    e.preventDefault();
    e.stopPropagation();
    setConfirmDelete(id);
  };

  const handleConfirmDelete = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (confirmDelete) {
      onDeleteConversation(confirmDelete);
      setConfirmDelete(null);
    }
  };

  const handleCancelDelete = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setConfirmDelete(null);
  };

  const displayConversations = showArchived ? archivedConversations : conversations;

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          + New Conversation
        </button>
      </div>

      <button className="search-btn" onClick={onOpenSearch}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" />
          <path d="M21 21l-4.35-4.35" />
        </svg>
        <span>Search conversations</span>
        <kbd>⌘K</kbd>
      </button>

      <div className="sidebar-tabs">
        <button
          className={`sidebar-tab ${!showArchived ? 'active' : ''}`}
          onClick={() => onToggleShowArchived(false)}
        >
          Conversations ({conversations.length})
        </button>
        <button
          className={`sidebar-tab ${showArchived ? 'active' : ''}`}
          onClick={() => onToggleShowArchived(true)}
        >
          Archived ({archivedConversations.length})
        </button>
      </div>

      <div className="conversation-list">
        {displayConversations.length === 0 ? (
          <div className="no-conversations">
            {showArchived ? 'No archived conversations' : 'No conversations yet'}
          </div>
        ) : (
          displayConversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item-wrapper ${
                conv.id === currentConversationId ? 'active' : ''
              }`}
            >
              {confirmDelete === conv.id ? (
                <div className="delete-confirm">
                  <span className="delete-confirm-text">Delete?</span>
                  <button
                    className="delete-confirm-btn yes"
                    onClick={handleConfirmDelete}
                    title="Confirm delete"
                  >
                    Yes
                  </button>
                  <button
                    className="delete-confirm-btn no"
                    onClick={handleCancelDelete}
                    title="Cancel"
                  >
                    No
                  </button>
                </div>
              ) : (
                <a
                  href={`?conversation=${conv.id}`}
                  className="conversation-item"
                  onClick={(e) => handleConversationClick(e, conv.id)}
                >
                  <div className="conversation-content">
                    <div className="conversation-title">
                      {conv.title || 'New Conversation'}
                    </div>
                    <div className="conversation-meta">
                      {conv.message_count} messages
                    </div>
                  </div>
                  <div className="conversation-actions">
                    {showArchived ? (
                      <button
                        className="action-btn unarchive"
                        onClick={(e) => handleUnarchive(e, conv.id)}
                        title="Restore conversation"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/>
                          <path d="M3 3v5h5"/>
                        </svg>
                      </button>
                    ) : (
                      <button
                        className="action-btn archive"
                        onClick={(e) => handleArchive(e, conv.id)}
                        title="Archive conversation"
                      >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <rect x="2" y="3" width="20" height="5" rx="1"/>
                          <path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/>
                          <path d="M10 12h4"/>
                        </svg>
                      </button>
                    )}
                    <button
                      className="action-btn delete"
                      onClick={(e) => handleDeleteClick(e, conv.id)}
                      title="Delete conversation"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M3 6h18"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
                        <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                      </svg>
                    </button>
                  </div>
                </a>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
