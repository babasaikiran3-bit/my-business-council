import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage2.css';

function deAnonymizeText(text, labelToModel) {
  if (!labelToModel) return text;

  let result = text;
  // Replace each "Response X" with the actual model name
  Object.entries(labelToModel).forEach(([label, model]) => {
    const modelShortName = model.split('/')[1] || model;
    result = result.replace(new RegExp(label, 'g'), `**${modelShortName}**`);
  });
  return result;
}

function ScoreCard({ evaluation, labelToModel }) {
  if (!evaluation) return null;

  return (
    <div className="scorecards-container">
      {Object.entries(evaluation).map(([label, metrics]) => {
        const targetModel = labelToModel && labelToModel[label]
          ? (labelToModel[label].split('/')[1] || labelToModel[label])
          : label;

        return (
          <div key={label} className="scorecard">
            <h4>Evaluation of {targetModel}</h4>
            <div className="metric-grid">
              {Object.entries(metrics).map(([metric, data]) => (
                <div key={metric} className="metric-item">
                  <div className="metric-header">
                    <span className="metric-name">{metric.replace('_', ' ')}</span>
                    <span className={`metric-score score-${Math.round(data.score)}`}>
                      {data.score}/10
                    </span>
                  </div>
                  <div className="metric-reasoning">{data.reasoning}</div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function Stage2({ rankings, labelToModel }) {
  const [activeTab, setActiveTab] = useState(0);

  if (!rankings || rankings.length === 0) {
    return null;
  }

  return (
    <div className="stage stage2">

      <p className="stage-description">
        Each model evaluated the others on Toxicity, Bias, Hallucination, and Political Leaning.
      </p>

      <div className="tabs">
        {rankings.map((rank, index) => (
          <button
            key={index}
            className={`tab ${activeTab === index ? 'active' : ''}`}
            onClick={() => setActiveTab(index)}
          >
            {rank.model.split('/')[1] || rank.model}
          </button>
        ))}
      </div>

      <div className="tab-content">
        <div className="ranking-model">
          Evaluator: {rankings[activeTab].model.split('/')[1] || rankings[activeTab].model}
        </div>

        <ScoreCard
          evaluation={rankings[activeTab].evaluation}
          labelToModel={labelToModel}
        />

        <div className="raw-response-toggle">
          <details>
            <summary>View Raw Response</summary>
            <div className="ranking-content markdown-content">
              <ReactMarkdown>
                {deAnonymizeText(rankings[activeTab].raw_response, labelToModel)}
              </ReactMarkdown>
            </div>
          </details>
        </div>
      </div>
    </div>
  );
}
