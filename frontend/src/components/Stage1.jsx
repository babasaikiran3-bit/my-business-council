import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { makeSafeMarkdownComponents } from './markdownComponents';
import { Users } from './Icons';
import './Stage1.css';

export default function Stage1({ responses }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!responses || responses.length === 0) {
    return null;
  }

  const components = makeSafeMarkdownComponents(responses[activeTab].sources);

  return (
    <div className="stage stage1">
      <h3 className="stage-title">
        <Users size={17} />
        <span>패널 각자의 답변</span>
      </h3>

      <div className="tabs">
        {responses.map((resp, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {resp.model.split('/')[1] || resp.model}
          </button>
        ))}
      </div>

      <div className="tab-content">
        <div className="model-name">{responses[activeTab].model}</div>
        <div className="response-text markdown-content">
          <ReactMarkdown components={components}>
            {responses[activeTab].response}
          </ReactMarkdown>
        </div>

        {responses[activeTab].sources &&
          responses[activeTab].sources.length > 0 && (
            <div className="source-chips">
              {responses[activeTab].sources.map((source, i) => (
                <a
                  key={i}
                  className="source-chip"
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {source.title || source.url}
                </a>
              ))}
            </div>
          )}
      </div>
    </div>
  );
}
