import ReactMarkdown from 'react-markdown';
import './ConsensusPreview.css';

/**
 * Previsualización del documento de consenso ANTES de escribirlo en el repo.
 * El chairman lo generó como texto (no tocó el disco); recién al aprobar el
 * backend lo escribe en docs/council/.
 */
export default function ConsensusPreview({ preview, repoPath, busy, onApprove, onDiscard }) {
  if (!preview) return null;

  return (
    <div className="cpreview-overlay" onMouseDown={() => !busy && onDiscard()}>
      <div className="cpreview-modal" onMouseDown={(e) => e.stopPropagation()}>
        <div className="cpreview-head">
          <div>
            <h3>Previsualización del consenso</h3>
            <div className="cpreview-target">
              Se escribirá en <code>{repoPath}/{preview.path}</code>
            </div>
          </div>
          <button className="cpreview-close" onClick={() => !busy && onDiscard()} disabled={busy}>✕</button>
        </div>

        <div className="cpreview-body">
          <div className="markdown-content">
            <ReactMarkdown>{preview.content}</ReactMarkdown>
          </div>
        </div>

        <div className="cpreview-actions">
          <span className="cpreview-note">Nada se escribe hasta que apruebes.</span>
          <div className="cpreview-buttons">
            <button className="cpreview-discard" onClick={onDiscard} disabled={busy}>
              Descartar
            </button>
            <button className="cpreview-approve" onClick={onApprove} disabled={busy}>
              {busy ? 'Escribiendo…' : '✅ Aprobar y escribir'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
