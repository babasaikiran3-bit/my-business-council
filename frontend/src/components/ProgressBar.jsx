import './ProgressBar.css';

export default function ProgressBar({ completed, total, stageName }) {
  const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
  
  return (
    <div className="progress-bar-container">
      <div className="progress-bar-header">
        <span className="progress-bar-label">{stageName}</span>
        <span className="progress-bar-count">{completed} / {total} agents</span>
      </div>
      <div className="progress-bar-track">
        <div 
          className="progress-bar-fill" 
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div className="progress-bar-percentage">{percentage}%</div>
    </div>
  );
}

