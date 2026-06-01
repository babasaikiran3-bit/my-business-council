import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { makeSafeMarkdownComponents } from './markdownComponents';
import { ChevronDown, BookOpen } from './Icons';
import './Stage0.css';

export default function Stage0({ evidenceBrief, sources }) {
  const [open, setOpen] = useState(false);

  const hasSources = sources && sources.length > 0;
  if (!evidenceBrief && !hasSources) {
    return null;
  }

  const components = makeSafeMarkdownComponents(sources);

  return (
    <div className="stage stage0">
      <button
        className="stage0-toggle"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
      >
        <span className="stage-title stage0-title">
          <BookOpen size={17} />
          <span>확인한 자료 · 근거 요약</span>
        </span>
        <ChevronDown
          size={18}
          className={`stage0-chevron ${open ? 'open' : ''}`}
        />
      </button>

      {open && (
        <div className="stage0-body">
          {evidenceBrief && (
            <div className="evidence-brief markdown-content">
              <ReactMarkdown components={components}>
                {evidenceBrief}
              </ReactMarkdown>
            </div>
          )}

          {hasSources && (
            <div className="stage0-sources">
              <h4 className="stage0-sources-title">확인한 출처</h4>
              <ul className="source-list">
                {sources.map((source, index) => (
                  <li key={index} className="source-item">
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
      )}
    </div>
  );
}
