import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
}) {
  const handleDelete = (e, conv) => {
    e.stopPropagation(); // no seleccionar la conversación al borrar
    if (window.confirm(`¿Borrar "${conv.title || 'New Conversation'}"? Esta acción no se puede deshacer.`)) {
      onDeleteConversation(conv.id);
    }
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
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
              <div className="conversation-body">
                <div className="conversation-title">
                  {conv.title || 'New Conversation'}
                </div>
                <div className="conversation-meta">
                  {conv.message_count} messages
                </div>
              </div>
              <button
                className="delete-conversation-btn"
                title="Borrar conversación"
                onClick={(e) => handleDelete(e, conv)}
              >
                🗑
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
