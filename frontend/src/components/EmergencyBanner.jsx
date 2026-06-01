import { AlertTriangle } from './Icons';
import './EmergencyBanner.css';

/**
 * High-contrast, deterministic emergency interstitial. Rendered the instant the
 * backend `emergency` SSE event arrives (before the ~30-60s pipeline) so a
 * panicking parent sees "call 119 / go to the ER" immediately. role="alert" makes
 * screen readers announce it at once.
 */
export default function EmergencyBanner({ triage }) {
  if (!triage) return null;

  return (
    <div className="emergency-banner" role="alert">
      <div className="emergency-banner-head">
        <span className="emergency-banner-icon" aria-hidden="true">
          <AlertTriangle size={22} />
        </span>
        <span className="emergency-banner-title">
          {triage.title_ko || '응급 상황일 수 있습니다'}
        </span>
      </div>
      {triage.message_ko && (
        <p className="emergency-banner-message">{triage.message_ko}</p>
      )}
      {triage.numbers && triage.numbers.length > 0 && (
        <div className="emergency-banner-numbers">
          {triage.numbers.map((n, i) => (
            <a
              key={i}
              className="emergency-number"
              href={`tel:${String(n).replace(/[^0-9]/g, '')}`}
            >
              {n}
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
