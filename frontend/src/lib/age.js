/**
 * Age helpers. The product stores a child's birthdate at year+month granularity
 * (YYYY-MM-01) and derives a human age label for display. The safety-relevant
 * age_days is computed server-side from the birthdate.
 */

/** Build the stored birthdate string from a year + month (1-12). Day is pinned to 01. */
export function toBirthdate(year, month) {
  const mm = String(month).padStart(2, '0');
  return `${year}-${mm}-01`;
}

/** Parse a YYYY-MM-DD birthdate back to { year, month } for editing. */
export function fromBirthdate(birthdate) {
  if (!birthdate) return { year: null, month: null };
  const [y, m] = birthdate.split('-');
  return { year: Number(y), month: Number(m) };
}

/** Whole months between a birthdate and now (clamped at 0). */
export function monthsOld(birthdate) {
  const { year, month } = fromBirthdate(birthdate);
  if (!year || !month) return 0;
  const now = new Date();
  return Math.max(0, (now.getFullYear() - year) * 12 + (now.getMonth() + 1 - month));
}

/** Warm Korean age label: "3개월", "11개월", "2세 4개월", "5세". */
export function ageLabel(birthdate) {
  const m = monthsOld(birthdate);
  if (m < 12) return `${m}개월`;
  const years = Math.floor(m / 12);
  const rem = m % 12;
  return rem === 0 ? `${years}세` : `${years}세 ${rem}개월`;
}

/** Derive age_days from a birthdate (fallback only; the server is the source of truth). */
export function ageDays(birthdate) {
  const { year, month } = fromBirthdate(birthdate);
  if (!year || !month) return null;
  const born = new Date(year, month - 1, 1);
  return Math.max(0, Math.floor((Date.now() - born.getTime()) / 86400000));
}

/** A friendly fallback display name when the parent left the name blank. */
export function childDisplayName(child) {
  return child && child.name ? child.name : '우리 아이';
}
