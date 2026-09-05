import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage2.css';

function renderCritiqueList(title, items) {
  if (!items || items.length === 0) {
    return null;
  }

  return (
    <div className="parsed-ranking">
      <strong>{title}:</strong>
      <ul>
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export default function Stage2({ critiques, labelToModel, structuredSummary }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!critiques || critiques.length === 0) {
    return null;
  }

  const active = critiques[activeTab];

  return (
    <div className="stage stage2">
      <h3 className="stage-title">Developer Mode: Structured Peer Critiques</h3>
      <p className="stage-description">
        Internal critiques are anonymous at synthesis time and shown here only in Developer Mode.
      </p>

      <div className="tabs">
        {critiques.map((critique, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {critique.model.split('/')[1] || critique.model}
          </button>
        ))}
      </div>

      <div className="tab-content">
        <div className="ranking-model">{active.model}</div>
        <div className="ranking-content markdown-content">
          <ReactMarkdown>{active.critique || ''}</ReactMarkdown>
        </div>

        {(active.structured_critiques || []).map((item, idx) => (
          <div key={idx} className="parsed-ranking">
            <strong>
              {item.response_label}
              {labelToModel?.[item.response_label]
                ? ` (${labelToModel[item.response_label]})`
                : ''}
            </strong>
            {renderCritiqueList('Strengths', item.strengths)}
            {renderCritiqueList('Weaknesses', item.weaknesses)}
            {renderCritiqueList('Missing Information', item.missing_information)}
            {renderCritiqueList('Unsupported Claims', item.unsupported_claims)}
            {renderCritiqueList('Suggested Improvements', item.suggested_improvements)}
          </div>
        ))}
      </div>

      {structuredSummary && structuredSummary.length > 0 && (
        <div className="aggregate-rankings">
          <h4>Aggregated Critique Summary</h4>
          {structuredSummary.map((summary, index) => (
            <div key={index} className="aggregate-item">
              <span className="rank-position">{summary.response_label}</span>
              <span className="rank-count">
                {labelToModel?.[summary.response_label]
                  ? labelToModel[summary.response_label]
                  : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
