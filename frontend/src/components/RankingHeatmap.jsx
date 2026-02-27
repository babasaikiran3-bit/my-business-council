import './RankingHeatmap.css';

function shortName(model) {
  return model.split('/')[1] || model;
}

function ordinal(n) {
  if (n === 1) return '1st';
  if (n === 2) return '2nd';
  if (n === 3) return '3rd';
  return `${n}th`;
}

/**
 * Renders a color-coded N×N heatmap showing how each council model
 * ranked every other model in Stage 2.
 *
 * Props:
 *   rankings      – Stage 2 rankings array: [{model, parsed_ranking, ...}]
 *   labelToModel  – Map of "Response A" -> full model id
 */
export default function RankingHeatmap({ rankings, labelToModel }) {
  if (!rankings || !labelToModel || rankings.length === 0) return null;

  // Rankees in label order (A, B, C …)
  const rankeeModels = Object.entries(labelToModel)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([, model]) => model);

  const rankerModels = rankings.map((r) => r.model);

  // Build position matrix: positions[rankerModel][rankeeModel] = 1-based rank
  const positions = {};
  for (const ranking of rankings) {
    positions[ranking.model] = {};
    const parsed = ranking.parsed_ranking || [];
    parsed.forEach((label, idx) => {
      const model = labelToModel[label];
      if (model) positions[ranking.model][model] = idx + 1;
    });
  }

  // Average rank per rankee (excluding self-votes)
  const avgRanks = {};
  for (const rankee of rankeeModels) {
    const vals = rankerModels
      .filter((r) => r !== rankee)
      .map((r) => positions[r]?.[rankee])
      .filter((v) => v !== undefined);
    if (vals.length > 0) {
      avgRanks[rankee] = (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1);
    }
  }

  return (
    <div className="ranking-heatmap">
      <h4>Ranking Heatmap</h4>
      <p className="heatmap-description">
        How each model ranked the others. Green = ranked 1st, red = ranked last.
        Lower average rank = stronger peer-evaluated performance.
      </p>
      <div className="heatmap-table-wrapper">
        <table className="heatmap-table">
          <thead>
            <tr>
              <th className="heatmap-corner">Ranker ↓ / Rankee →</th>
              {rankeeModels.map((model) => (
                <th key={model} className="heatmap-col-header">
                  {shortName(model)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rankerModels.map((ranker) => (
              <tr key={ranker}>
                <td className="heatmap-row-header">{shortName(ranker)}</td>
                {rankeeModels.map((rankee) => {
                  if (ranker === rankee) {
                    return (
                      <td key={rankee} className="heatmap-cell heatmap-self">
                        —
                      </td>
                    );
                  }
                  const pos = positions[ranker]?.[rankee];
                  if (pos === undefined) {
                    return (
                      <td key={rankee} className="heatmap-cell heatmap-unknown">
                        ?
                      </td>
                    );
                  }
                  return (
                    <td
                      key={rankee}
                      className={`heatmap-cell heatmap-pos-${pos}`}
                    >
                      {ordinal(pos)}
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr className="heatmap-avg-row">
              <td className="heatmap-row-header heatmap-avg-label">Avg Rank</td>
              {rankeeModels.map((rankee) => (
                <td key={rankee} className="heatmap-cell heatmap-avg">
                  {avgRanks[rankee] ?? '—'}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
