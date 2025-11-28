import './CostDisplay.css';

export default function CostDisplay({ costs }) {
  if (!costs) {
    return null;
  }

  const formatCost = (usd) => {
    if (usd === 0) return '$0.00';
    if (usd < 0.01) return `$${usd.toFixed(6)}`;
    return `$${usd.toFixed(4)}`;
  };

  return (
    <div className="cost-display">
      <div className="cost-header">
        <span className="cost-icon">💰</span>
        <span className="cost-title">Request Cost</span>
      </div>
      <div className="cost-breakdown">
        <div className="cost-item">
          <span className="cost-label">Stage 1 (Individual Responses):</span>
          <span className="cost-value">{formatCost(costs.stage1_usd)}</span>
        </div>
        <div className="cost-item">
          <span className="cost-label">Stage 2 (Peer Rankings):</span>
          <span className="cost-value">{formatCost(costs.stage2_usd)}</span>
        </div>
        <div className="cost-item">
          <span className="cost-label">Stage 3 (Final Synthesis):</span>
          <span className="cost-value">{formatCost(costs.stage3_usd)}</span>
        </div>
        <div className="cost-item cost-total">
          <span className="cost-label">Total:</span>
          <span className="cost-value">{formatCost(costs.total_usd)}</span>
        </div>
      </div>
    </div>
  );
}
