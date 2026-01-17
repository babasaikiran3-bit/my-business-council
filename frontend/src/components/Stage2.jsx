import { useState, memo } from 'react';
import Markdown from './Markdown';
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

export default memo(function Stage2({ rankings, labelToModel, aggregateRankings }) {
  const [activeTab, setActiveTab] = useState(0);
  const [isExpanded, setIsExpanded] = useState(false);

  if (!rankings || rankings.length === 0) {
    return null;
  }

  // Get top ranked model for summary
  const topModel = aggregateRankings?.[0]?.model?.split('/')[1] || aggregateRankings?.[0]?.model;

  return (
    <div className={`stage stage2 ${isExpanded ? 'expanded' : 'collapsed'}`}>
      <button
        className="stage-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <h3 className="stage-title">Stage 2: Peer Rankings</h3>
        <span className="stage-summary">
          {topModel ? `Top: ${topModel}` : `${rankings.length} evaluations`}
        </span>
        <svg
          className={`expand-icon ${isExpanded ? 'expanded' : ''}`}
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {isExpanded && (
        <div className="stage-content">
          {topModel && (
            <div className="winner-banner">
              <span className="winner-icon">🏆</span>
              <span className="winner-label">Council's Top Pick:</span>
              <span className="winner-model">{topModel}</span>
            </div>
          )}
          <h4>Raw Evaluations</h4>
          <p className="stage-description">
            Each model evaluated all responses (anonymized as Response A, B, C, etc.) and provided rankings.
            Below, model names are shown in <strong>bold</strong> for readability, but the original evaluation used anonymous labels.
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
              {rankings[activeTab].model}
            </div>
            <div className="ranking-content">
              <Markdown>{deAnonymizeText(rankings[activeTab].ranking, labelToModel)}</Markdown>
            </div>

            {rankings[activeTab].parsed_ranking &&
             rankings[activeTab].parsed_ranking.length > 0 && (
              <div className="parsed-ranking">
                <strong>Extracted Ranking:</strong>
                <ol>
                  {rankings[activeTab].parsed_ranking.map((label, i) => (
                    <li key={i}>
                      {labelToModel && labelToModel[label]
                        ? labelToModel[label].split('/')[1] || labelToModel[label]
                        : label}
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>

          {aggregateRankings && aggregateRankings.length > 0 && (
            <div className="aggregate-rankings">
              <h4>Aggregate Rankings (Street Cred)</h4>
              <p className="stage-description">
                Combined results across all peer evaluations (lower score is better):
              </p>
              <div className="aggregate-list">
                {aggregateRankings.map((agg, index) => (
                  <div key={index} className="aggregate-item">
                    <span className="rank-position">#{index + 1}</span>
                    <span className="rank-model">
                      {agg.model.split('/')[1] || agg.model}
                    </span>
                    <span className="rank-score">
                      Avg: {agg.average_rank.toFixed(2)}
                    </span>
                    <span className="rank-count">
                      ({agg.rankings_count} votes)
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
});
