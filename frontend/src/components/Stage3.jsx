import ReactMarkdown from 'react-markdown';
import { makeSafeMarkdownComponents } from './markdownComponents';
import { BadgeCheck, AlertTriangle, BookOpen, ExternalLink } from './Icons';
import './Stage3.css';

/**
 * Pull an "> EMERGENCY:" / "> 응급:" callout out of the answer so it can be pinned,
 * in high contrast, at the very top — guaranteeing a panicked parent sees it
 * regardless of where the model placed it in the markdown. Returns the callout
 * text plus the body with that blockquote removed (so it isn't shown twice).
 *
 * NOTE: a separator (colon/space) is required after the keyword instead of a
 * regex word boundary (\b) — \b is ASCII-only and never fires after a Korean
 * syllable, which previously left the Korean "응급:" callout un-pinned.
 */
function parseAnswer(text) {
  if (!text) return { emergency: null, body: '' };
  const lines = text.split('\n');
  for (let i = 0; i < lines.length; i++) {
    const stripped = lines[i].replace(/^\s*>?\s*\**\s*/, '');
    const m = stripped.match(/^(?:EMERGENCY|응급)[\s:：]+(.*)$/i);
    if (m) {
      let msg = m[1] || '';
      let last = i;
      // Gather any continuation lines of the same blockquote.
      for (let j = i + 1; j < lines.length; j++) {
        if (/^\s*>/.test(lines[j])) {
          msg += ' ' + lines[j].replace(/^\s*>\s?/, '');
          last = j;
        } else {
          break;
        }
      }
      const emergency =
        msg.replace(/\*+/g, '').trim() ||
        '응급 상황일 수 있어요 — 지금 바로 진료를 받으세요.';
      const body = [...lines.slice(0, i), ...lines.slice(last + 1)]
        .join('\n')
        .replace(/^\s+/, '');
      return { emergency, body };
    }
  }
  return { emergency: null, body: text };
}

export default function Stage3({ finalResponse }) {
  if (!finalResponse) {
    return null;
  }

  const components = makeSafeMarkdownComponents(finalResponse.sources);
  const { emergency, body } = parseAnswer(finalResponse.response);
  const hasSources = finalResponse.sources && finalResponse.sources.length > 0;

  return (
    <article className="answer-card">
      <div className="answer-card-header">
        <span className="answer-badge" aria-hidden="true">
          <BadgeCheck size={18} />
        </span>
        <div className="answer-card-heading">
          <span className="answer-card-title">라운드테이블의 답변</span>
          <span className="answer-card-sub">신뢰할 수 있는 출처로 검토했어요</span>
        </div>
      </div>

      {emergency && (
        <div className="answer-emergency" role="alert">
          <AlertTriangle size={20} />
          <span className="answer-emergency-text">
            <strong>응급:</strong> {emergency}
          </span>
        </div>
      )}

      <div className="answer-body markdown-content">
        <ReactMarkdown components={components}>{body}</ReactMarkdown>
      </div>

      {hasSources && (
        <div className="answer-sources">
          <h4 className="answer-sources-title">
            <BookOpen size={16} />
            <span>참고한 출처</span>
          </h4>
          <ul className="answer-source-list">
            {finalResponse.sources.map((source, index) => (
              <li key={index}>
                <a
                  className="answer-source-link"
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <span className="answer-source-text">
                    {source.title || source.url}
                  </span>
                  <ExternalLink size={14} />
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}
