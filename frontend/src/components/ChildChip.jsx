import './ChildChip.css';
import { ageLabel, childDisplayName } from '../lib/age';

/**
 * The persistent child-context chip above the composer. Replaces the old age-pill row:
 * age is derived from the saved child's birthdate, confirmed here, and editable on tap.
 */
export default function ChildChip({ child, onClick }) {
  if (!child) {
    return (
      <button type="button" className="child-chip child-chip--empty" onClick={onClick}>
        <span className="child-chip-plus" aria-hidden="true">＋</span>
        <span>아이 정보 추가하기</span>
      </button>
    );
  }
  return (
    <button type="button" className="child-chip" onClick={onClick} aria-label="아이 정보 수정">
      <span className="child-chip-dot" aria-hidden="true" />
      <span className="child-chip-name">{childDisplayName(child)}</span>
      <span className="child-chip-sep" aria-hidden="true">·</span>
      <span className="child-chip-age">{ageLabel(child.birthdate)}</span>
      <span className="child-chip-caret" aria-hidden="true">›</span>
    </button>
  );
}
