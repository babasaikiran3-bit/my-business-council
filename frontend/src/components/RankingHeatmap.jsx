import './RankingHeatmap.css';

function shortName(model) {
  return model.split('/')[1] || model;
}

function ordinal(position) {
  if (position === 1) return '1st';
  if (position === 2) return '2nd';
  if (position === 3) return '3rd';
  return `${position}th`;
}

export default function RankingHeatmap({ rankings, labelToModel }) {
  if (!rankings || !labelToModel || rankings.length === 0) {
    return null;
  }

  const rankeeModels = Object.entries(labelToModel)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([, model]) => model);

  const rankerModels = rankings.map((ranking) => ranking.model);

  const positions = {};
  for (const ranking of rankings) {
    positions[ranking.model] = {};
    const parsedRanking = ranking.parsed_ranking || [];
    parsedRanking.forEach((label, index) => {
      const model = labelToModel[label];
      if (model) {
        positions[ranking.model][model] = index + 1;
      }
    });
  }

  const averageRanks = {};
  for (const rankee of rankeeModels) {
    const values = rankerModels
      .filter((ranker) => ranker !== rankee)
      .map((ranker) => positions[ranker]?.[rankee])
      .filter((value) => value !== undefined);

    if (values.length > 0) {
      averageRanks[rankee] = (values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1);
    }
  }

  return (
    <div className="ranking-heatmap">
      <h4>Ranking Heatmap</h4>
      <p className="heatmap-description">
        How each model ranked the others. Green means 1st place, red means lower placement.
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
                        -
                      </td>
                    );
                  }

                  const position = positions[ranker]?.[rankee];
                  if (position === undefined) {
                    return (
                      <td key={rankee} className="heatmap-cell heatmap-unknown">
                        ?
                      </td>
                    );
                  }

                  return (
                    <td
                      key={rankee}
                      className={`heatmap-cell heatmap-pos-${position}`}
                    >
                      {ordinal(position)}
                    </td>
                  );
                })}
              </tr>
            ))}
            <tr className="heatmap-avg-row">
              <td className="heatmap-row-header">Avg Rank</td>
              {rankeeModels.map((rankee) => (
                <td key={rankee} className="heatmap-cell heatmap-avg">
                  {averageRanks[rankee] ?? '-'}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}