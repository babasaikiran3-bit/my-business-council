import ReactMarkdown from 'react-markdown';
import { makeSafeMarkdownComponents } from './markdownComponents';
import './Stage3.css';

/**
 * Pull an "> EMERGENCY:" callout out of the answer so it can be pinned, in
 * high contrast, at the very top — guaranteeing a panicked parent sees it
 * regardless of where the model placed it in the markdown.
 */
function extractEmergency(text) {
  if (!text) return null;
  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const stripped = lines[i].replace(/^\s*>?\s*\**\s*/, '');
    const m = stripped.match(/^EMERGENCY\b[:：]?\s*(.*)$/i);
    if (m) {
      let msg = m[1] || '';
      // Gather any continuation lines of the same blockquote.
      for (let j = i + 1; j < lines.length; j++) {
        if (/^\s*>/.test(lines[j])) {
          msg += ' ' + lines[j].replace(/^\s*>\s?/, '');
        } else {
          break;
        }
      }
      return msg.replace(/\*+/g, '').trim() ||
        'This may be an emergency — seek medical care now.';
    }
  }
  return null;
}

export default function Stage3({ finalResponse }) {
  if (!finalResponse) {
    return null;
  }

  const components = makeSafeMarkdownComponents(finalResponse.sources);
  const emergency = extractEmergency(finalResponse.response);

  return (
    <div className="stage stage3">
      <h3 className="stage-title">Stage 3: Final Council Answer</h3>
      <div className="final-response">
        <div className="chairman-label">
          Chairman: {finalResponse.model.split('/')[1] || finalResponse.model}
        </div>

        {emergency && (
          <div className="stage3-emergency" role="alert">
            <span className="stage3-emergency-icon" aria-hidden="true">
              ⚠️
            </span>
            <span className="stage3-emergency-text">
              <strong>EMERGENCY:</strong> {emergency}
            </span>
          </div>
        )}

        <div className="final-text markdown-content">
          <ReactMarkdown components={components}>
            {finalResponse.response}
          </ReactMarkdown>
        </div>

        {finalResponse.sources && finalResponse.sources.length > 0 && (
          <div className="stage3-sources">
            <h4 className="stage3-sources-title">Sources</h4>
            <ul className="stage3-source-list">
              {finalResponse.sources.map((source, index) => (
                <li key={index} className="stage3-source-item">
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {source.title || source.url}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
