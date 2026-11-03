// Official DB78 candidate condition values: preserve Y/N/NULL (never coerce NULL to N).
export const CONDITION_KEYS = Object.freeze(['result', 'hazard', 'exposure', 'vulnerable']);
export const CONDITION_LABELS = Object.freeze({result:'종합', hazard:'위험', exposure:'노출', vulnerable:'취약'});
export function conditionValue(value) {
  if (value === 'Y' || value === 'N') return value;
  if (value === null || value === undefined) return 'NULL';
  return 'INVALID';
}
export function filterLiveCandidates(rows, query, filters) {
  const q = String(query || '').trim().toLowerCase();
  return rows.filter(row => {
    if (q && !String(row.gid ?? '').toLowerCase().includes(q) &&
        !String(row.gu ?? '').toLowerCase().includes(q)) return false;
    return CONDITION_KEYS.every(key => !filters[key] ||
      conditionValue(row.conditions?.[key]) === filters[key]);
  });
}
export function matchedRoleText(value) {
  if (value === null || value === undefined || value === '') return '없음';
  if (Array.isArray(value)) return value.length ? value.join(', ') : '없음';
  return typeof value === 'string' ? value : JSON.stringify(value);
}
