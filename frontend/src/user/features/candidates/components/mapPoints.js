import L from 'leaflet';

/** 한 칸 안의 민원 점이 이 수를 넘으면 가까운 점을 숫자 원으로 묶는다 (ISS-038, 가정값) */
export const CLUSTER_LIMIT = 300;

/** 점 종류: exact ● 민원 원본 좌표, near ○ 민원 근처 위치, site ■ 민원이 아닌 근거 지점 (US-01 1-5, ISS-036) */
export const pointKind = (p) => (p.kind === 'site' ? 'site' : p.near ? 'near' : 'exact');

/** 점 아이콘(지름 8px, 흰 테두리 1.5px). 점은 진한 한 색이고 모양으로만 나눈다. 같은 좌표의 민원 건수는 점 옆에 숫자로 붙인다. */
export function pointIcon(kind, count = 1) {
  const badge = count > 1 ? `<span class="rmap-point-count">${count}</span>` : '';
  return L.divIcon({
    className: 'rmap-point-wrap',
    html: `<span class="rmap-point rmap-point--${kind}"></span>${badge}`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  });
}

/** 가까운 민원 점 묶음 아이콘. 숫자는 묶인 민원 건수이고, 건수가 클수록 조금 크다. */
export function clusterIcon(n) {
  const size = n >= 1000 ? 36 : n >= 100 ? 32 : n >= 20 ? 28 : 24;
  return L.divIcon({
    className: 'rmap-point-wrap',
    html: `<span class="rmap-cluster" style="width:${size}px;height:${size}px">${n}</span>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

/** 말풍선 글자: %보행 문제 유형% %건수%건%근처 위치 표시% (○ 점일 때만 ' · 근처 위치') */
export function pointLabel(p) {
  if (p.kind === 'site') return p.issue;
  return `${p.type} ${p.count}건${p.near ? ' · 근처 위치' : ''}`;
}

export const clusterLabel = (g) => `민원 ${g.count}건 · 원본 좌표 ${g.exact}건 · 근처 위치 ${g.near}건`;

/** 확대 단계마다 묶는 화면 거리(px). 많이 확대할수록 잘게 나뉜다. */
const clusterPixel = (zoom) => (zoom < 16 ? 56 : zoom < 17 ? 44 : 34);

/**
 * 민원 점을 화면 거리로 묶는다. 한 점뿐인 칸은 그대로 두고, 둘 이상이면 묶음이 된다.
 * 돌려주는 값: [{ single: 점 }] 또는 [{ members, count, exact, near, lat, lon }]
 */
export function groupComplaintPoints(map, points, zoom) {
  const size = clusterPixel(zoom);
  const cells = new Map();
  points.forEach((p) => {
    const pt = map.project([p.lat, p.lon], zoom);
    const key = `${Math.floor(pt.x / size)}:${Math.floor(pt.y / size)}`;
    const g = cells.get(key);
    if (g) g.push(p);
    else cells.set(key, [p]);
  });
  return [...cells.values()].map((members) => {
    if (members.length === 1) return { single: members[0] };
    const count = members.reduce((s, p) => s + p.count, 0);
    const near = members.filter((p) => p.near).reduce((s, p) => s + p.count, 0);
    const lat = members.reduce((s, p) => s + p.lat * p.count, 0) / count;
    const lon = members.reduce((s, p) => s + p.lon * p.count, 0) / count;
    return { members, count, exact: count - near, near, lat, lon };
  });
}

/** 범례의 "이 칸의 근거: %보행 문제 유형% %건수% · …" 한 줄. 건수가 큰 유형부터 4개까지. */
export function basisSummary(cell) {
  const sums = new Map();
  (cell.complaintPoints || []).forEach((p) => sums.set(p.type, (sums.get(p.type) || 0) + p.count));
  (cell.points || []).forEach((p) => sums.set(p.label, (sums.get(p.label) || 0) + 1));
  return [...sums.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([name, n]) => `${name} ${n}`)
    .join(' · ');
}
