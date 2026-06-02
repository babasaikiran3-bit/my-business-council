import { Logo, AlertTriangle, BadgeCheck } from './Icons';
import './ExampleCard.css';

const SOURCES = ['대한소아청소년과학회', '질병관리청', 'AAP', 'CDC'];

/**
 * A static, rendered example of one real question → sources → answer, for the landing
 * page. The highest-trust element: it shows exactly what a parent will receive.
 */
export default function ExampleCard() {
  return (
    <div className="example-card">
      <div className="example-q">
        <span className="example-q-label">부모</span>
        <p>8개월 아기가 밤새 38.5도 열이 나요. 언제 병원에 가야 하나요?</p>
      </div>

      <div className="example-a">
        <div className="example-a-id">
          <span className="example-a-avatar"><Logo size={22} /></span>
          <span>부모 라운드테이블</span>
        </div>

        <div className="example-emergency">
          <AlertTriangle size={18} />
          <span>열성 경련, 처지거나 잘 먹지 못함, 호흡 곤란이 보이면 즉시 병원에 가세요.</span>
        </div>

        <p className="example-a-body">
          생후 8개월 아기의 38.5도 발열은 대부분 바이러스 감염이 원인이에요. 아이가 잘 놀고
          수분을 잘 섭취한다면 집에서 경과를 관찰할 수 있지만, <strong>열이 48시간 이상
          지속</strong>되거나 위 응급 신호가 보이면 진료를 받으세요.
        </p>

        <div className="example-sources">
          <span className="example-sources-label"><BadgeCheck size={14} /> 출처</span>
          {SOURCES.map((s) => (
            <span key={s} className="example-source-chip">{s}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
