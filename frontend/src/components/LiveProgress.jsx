import './LiveProgress.css';

const TOOL_ICON = {
  Read: '📖', Grep: '🔍', Glob: '🔍', Bash: '🔧',
  Write: '✏️', Edit: '✏️', MCP: '🧩',
};

const STATUS_ICON = { working: '⏳', done: '✅', error: '❌' };

/**
 * Panel en vivo del progreso de cada agente durante Stage 1.
 * agents: { [model]: { status, tool, detail, thought } }
 */
export default function LiveProgress({ agents, stageLabel }) {
  const ids = Object.keys(agents || {});
  if (ids.length === 0) return null;

  return (
    <div className="live-progress">
      <div className="live-header">
        <span className="live-dot" /> En vivo {stageLabel ? `· ${stageLabel}` : ''}
      </div>
      <div className="live-rows">
        {ids.map((id) => {
          const a = agents[id];
          const icon = a.status === 'working'
            ? (a.tool ? (TOOL_ICON[a.tool] || '🛠️') : STATUS_ICON.working)
            : (STATUS_ICON[a.status] || '•');
          let line;
          if (a.status === 'done') line = 'terminó';
          else if (a.status === 'error') line = a.reason || 'error';
          else if (a.tool) line = `${a.tool} ${a.detail || ''}`;
          else if (a.thought) line = a.thought;
          else line = 'trabajando…';
          return (
            <div key={id} className={`live-row ${a.status}`}>
              <span className="live-model">{id}</span>
              <span className="live-icon">{icon}</span>
              <span className="live-line" title={line}>{line}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
