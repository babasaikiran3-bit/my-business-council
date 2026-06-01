import { useState, useEffect } from 'react';
import { Sparkle } from './Icons';
import './CalmProgress.css';

// A calm, reassuring wait — one gentle indicator plus rotating tips — instead of
// four technical stage spinners. Mixes parenting reassurance and how-to-use hints.
const TIPS = [
  '질병관리청·대한소아청소년과학회 등 신뢰할 수 있는 자료를 확인하고 있어요.',
  '여러 AI가 같은 근거를 함께 검토한 뒤, 하나의 답으로 정리해 드려요.',
  '팁: 아이 나이를 정확히 선택하면 더 안전하고 정확한 답을 받을 수 있어요.',
  '응급 신호(호흡곤란·경련·신생아 발열 등)는 기다리지 말고 즉시 119에 연락하세요.',
  '답변에는 참고한 출처가 함께 표시돼요. 직접 확인하실 수 있어요.',
];

export default function CalmProgress() {
  const [i, setI] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setI((n) => (n + 1) % TIPS.length), 3800);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="calm-progress" role="status" aria-live="polite">
      <div className="calm-progress-orb" aria-hidden="true">
        <Sparkle size={20} />
      </div>
      <div className="calm-progress-text">
        <p className="calm-progress-title">
          신뢰할 수 있는 답을 준비하고 있어요
          <span className="calm-dots" aria-hidden="true">
            <span></span>
            <span></span>
            <span></span>
          </span>
        </p>
        <p className="calm-progress-tip" key={i}>{TIPS[i]}</p>
      </div>
    </div>
  );
}
