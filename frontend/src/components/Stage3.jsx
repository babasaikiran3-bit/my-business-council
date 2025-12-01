import './Stage3.css';

export default function Stage3({ finalResponse }) {
  // finalResponse is now the scoreboard list
  const scoreboard = finalResponse;

  if (!scoreboard || !Array.isArray(scoreboard)) {
    return null;
  }

  return (
    <div className="stage stage3">

      <div className="scoreboard-container">
        <table className="scoreboard-table">
          <thead>
            <tr>
              <th>Model</th>
              <th>Avg Score</th>
              <th>Toxicity</th>
              <th>Bias</th>
              <th>Hallucination</th>
              <th>Political</th>
            </tr>
          </thead>
          <tbody>
            {scoreboard.map((entry, index) => (
              <tr key={index}>
                <td className="model-name">
                  {entry.model.split('/')[1] || entry.model}
                </td>
                <td className="avg-score">
                  {entry.average_score}
                </td>
                <td className={`score-cell score-${Math.round(entry.scores.toxicity)}`}>
                  {entry.scores.toxicity}
                </td>
                <td className={`score-cell score-${Math.round(entry.scores.bias)}`}>
                  {entry.scores.bias}
                </td>
                <td className={`score-cell score-${Math.round(entry.scores.hallucination)}`}>
                  {entry.scores.hallucination}
                </td>
                <td className={`score-cell score-${Math.round(entry.scores.political_leaning)}`}>
                  {entry.scores.political_leaning}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="scoreboard-legend">
          Scores are 0-10. Lower is generally "safer/neutral", except Political Leaning where 0 is Neutral.
        </p>
      </div>
    </div>
  );
}
