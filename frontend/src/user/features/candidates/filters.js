import { DECISION, RELIABILITY } from '../../../shared/constants.js';
import { LIST } from './copy.js';

export const EMPTY_FILTERS = {
  decision: '', // KPI 카드로 고른 결정 상태 (비어 있으면 전체)
  priorityOnly: false, // 시스템 제안 얼럿의 '확인하기': 우선 확인 조건에 맞은 곳만
  obstacles: [],
  reliability: [],
  zone: [],
  complaint: [],
};

const MORE_KEYS = ['obstacles', 'reliability', 'zone', 'complaint'];

/** 필터 펼침에서 고른 것의 꼬리표 목록 (KPI 카드와 얼럿은 자기 자리에서 선택 상태를 보인다) */
export function activeTags(f) {
  const tags = [];
  f.obstacles.forEach((v) => tags.push({ key: `ob-${v}`, text: v, clear: 'obstacles', value: v }));
  f.reliability.forEach((v) => tags.push({ key: `rel-${v}`, text: `${LIST.reliabilityLabel} ${v}`, clear: 'reliability', value: v }));
  f.zone.forEach((v) => tags.push({ key: `zone-${v}`, text: v, clear: 'zone', value: v }));
  f.complaint.forEach((v) => tags.push({ key: `cmp-${v}`, text: v, clear: 'complaint', value: v }));
  return tags;
}

export function clearTag(f, tag) {
  if (MORE_KEYS.includes(tag.clear)) return { ...f, [tag.clear]: f[tag.clear].filter((x) => x !== tag.value) };
  return f;
}

/** 필터를 적용한다. 같은 분류 안은 하나라도 맞으면(또는), 분류끼리는 모두 맞아야(그리고) 보인다.
 *  KPI(결정 상태)와 얼럿(우선 확인 조건)도 같은 규칙으로 함께 적용된다. */
export function applyFilters(rows, f, knownConditionIds = null) {
  return rows.filter((r) => {
    if (f.decision && r.decision !== f.decision) return false;
    if (f.priorityOnly && !isPriority(r, knownConditionIds)) return false;
    if (f.obstacles.length && !f.obstacles.some((o) => r.obstacleNames.includes(o))) return false;
    if (f.reliability.length && !f.reliability.includes(r.reliability)) return false;
    if (f.zone.length) {
      const label = r.inProtectionZone ? '보호구역 안' : '보호구역 밖';
      if (!f.zone.includes(label)) return false;
    }
    if (f.complaint.length) {
      const ok = f.complaint.some((c) => (c === '재발 있음' ? r.recur : r.complaintFlag === c));
      if (!ok) return false;
    }
    return true;
  });
}

/** 우선 확인 조건에 맞은 후보인가. 정해진 조건 번호만 센다. */
export function isPriority(r, knownIds) {
  return r.conditions.some((id) => !knownIds || knownIds.has(id));
}

const RELI_ORDER = Object.fromEntries(RELIABILITY.map((x, i) => [x, i]));
const DEC_ORDER = Object.fromEntries([DECISION.NONE, DECISION.TARGET, DECISION.EXCLUDE, DECISION.HOLD].map((x, i) => [x, i]));

const SORTERS = {
  rank: (r) => r.rank,
  gu: (r) => r.gu,
  address: (r) => r.address,
  score: (r) => r.score,
  obstacle: (r) => r.obstacleMain,
  reliability: (r) => RELI_ORDER[r.reliability],
  unrated: (r) => r.unratedCount,
  decision: (r) => DEC_ORDER[r.decision],
};

export function sortRows(rows, sort) {
  const get = SORTERS[sort.key] || SORTERS.rank;
  const dir = sort.dir === 'asc' ? 1 : -1;
  return [...rows].sort((a, b) => {
    const x = get(a);
    const y = get(b);
    if (x === y) return a.rank - b.rank;
    if (typeof x === 'string') return x.localeCompare(y, 'ko') * dir;
    return (x - y) * dir;
  });
}
