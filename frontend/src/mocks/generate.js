// 가짜 후보 데이터 생성기. 같은 코드는 항상 같은 결과를 낸다(고정 난수).
// 격자 위치(gid, 중심 좌표, 구, 동)만 DB v1.9 01_grid_cell에서 가져왔다. 점수·근거·결정은 모두 가짜다.
import raw from './data/seongnam_cells.json';
import { RUNS } from './runs.js';
import { DECISION, GU_LIST, RUN_STATUS } from '../shared/constants.js';

function mulberry32(seed) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const D_LAT = 250 / 111320; // 250m 격자 (ISS-003)
const D_LON = 250 / (111320 * Math.cos((37.4 * Math.PI) / 180));

export const DECISION_REASONS = [
  '이미 정비 계획에 있음',
  '현장 확인 결과 문제 없음',
  '다른 부서 소관',
  '예산·공정 사정',
  '기타',
];

/** 보행 방해요소 DB (가안). 조치 제안 표(US-14)의 행도 이 목록에서 나온다. */
export const OBSTACLES = [
  {
    key: 'sidewalk',
    name: '보도 폭 부족',
    problem: '보도 폭 2.0m 미만(도면)',
    check: '실제 걸을 수 있는 폭',
    action: '현장 실측',
    requestContent: '보도 폭 현장 실측',
    deptKind: 'road',
    sentence:
      '도면에서 잰 보도 폭이 2.0m보다 좁습니다. 실제로 걸을 수 있는 폭을 현장에서 재 주세요.',
    tableDept: '구 보도 담당 팀',
    article: '보도 설치 및 관리 지침 3.2',
  },
  {
    key: 'signal',
    name: '횡단보도 신호시간 판단 불가',
    problem: '횡단보도 신호시간 판단 불가',
    check: '보행 녹색시간',
    action: '신호 주기표 요청',
    requestContent: '보행 신호 주기표 확인',
    deptKind: 'traffic',
    sentence:
      '이 횡단보도는 보행 신호 시간을 자료로 확인하지 못했습니다. 경찰서에 신호 주기표를 요청해 보행 녹색시간을 확인해 주세요.',
    tableDept: '시 교통기획과 교통시설팀',
    article: null,
  },
  {
    key: 'light',
    name: '조도 부족',
    problem: '조도 부족(2022년 측정)',
    check: '야간 밝기',
    action: '현장 확인',
    requestContent: '야간 밝기 현장 확인',
    deptKind: 'light',
    sentence:
      '2022년 측정에서 이 횡단보도 주변 밝기가 기준값보다 낮게 나왔습니다. 밤에 불이 켜지는지, 어두운 구간이 있는지 현장에서 확인해 주세요.',
    tableDept: '구 도로조명팀',
    article: null,
  },
  {
    key: 'refuge',
    name: '중간 대피 공간 없음',
    problem: '중간 대피 공간 없음',
    check: '교통섬·분리대가 있는지',
    action: '현장 확인 후 교통섬·보행섬 검토 요청',
    requestContent: '교통섬·분리대 현장 확인',
    deptKind: 'unknown',
    sentence:
      '왕복 6차로 횡단보도인데 자료에는 중간 대피 공간이 없습니다. 교통섬이나 분리대가 실제로 있는지 현장에서 확인해 주세요.',
    tableDept: null, // 받는 부서 확인 필요
    article: null,
  },
  {
    key: 'parkSidewalk',
    name: '인도 불법 주정차',
    problem: '보행 관련 주정차 민원 쏠림·재발',
    check: '주정차 반복 여부',
    action: '현장 확인과 단속 요청',
    requestContent: '주정차 반복 여부 확인과 단속',
    deptKind: 'parking',
    sentence:
      '이번 회차 자료에 인도·횡단보도 불법 주정차 민원이 6건 있고, 2건은 다시 들어왔습니다. 지금도 주정차가 반복되는지 확인하고 단속을 요청해 주세요.',
    tableDept: '구 주차관리팀',
    article: '도로교통법 제32조',
  },
  {
    key: 'parkCross',
    name: '횡단보도 불법 주정차',
    problem: '보행 관련 주정차 민원 쏠림·재발',
    check: '주정차 반복 여부',
    action: '현장 확인과 단속 요청',
    requestContent: '주정차 반복 여부 확인과 단속',
    deptKind: 'parking',
    sentence:
      '이번 회차 자료에 인도·횡단보도 불법 주정차 민원이 6건 있고, 2건은 다시 들어왔습니다. 지금도 주정차가 반복되는지 확인하고 단속을 요청해 주세요.',
    tableDept: '구 주차관리팀',
    article: '도로교통법 제32조',
  },
];
const OB = Object.fromEntries(OBSTACLES.map((o) => [o.key, o]));

/** 담당 부서 표 (가안). 개인 담당자 이름은 넣지 않는다 (F-04). */
export function deptNameFor(kind, gu) {
  switch (kind) {
    case 'road':
      return `${gu} 건설과 도로관리팀`;
    case 'light':
      return `${gu} 건설과 도로조명팀`;
    case 'parking':
      return `${gu} 경제교통과 주차관리팀`;
    case 'traffic':
      return '시 교통기획과 교통시설팀';
    default:
      return null;
  }
}

export const DEPT_CONTACTS = {};
let phoneSeq = 1;
function contactOf(name) {
  if (!DEPT_CONTACTS[name]) {
    DEPT_CONTACTS[name] = `031-729-${String(phoneSeq++ * 7 + 1000).padStart(4, '0')}`;
  }
  return DEPT_CONTACTS[name];
}
export { contactOf };

/** 담당 부서 선택지 (담당 부서 표의 부서 목록) */
export const DEPT_OPTIONS = [
  ...GU_LIST.flatMap((gu) => [
    deptNameFor('road', gu),
    deptNameFor('light', gu),
    deptNameFor('parking', gu),
  ]),
  '분당구 건설과 보도관리팀',
  '시 교통기획과 교통시설팀',
  '시 도로과 도로관리팀',
];
DEPT_OPTIONS.forEach(contactOf);

export const PRIORITY_CONDITIONS = [
  { id: 'cA', name: '사고 다발지 3년 반복', ratio: 40 }, // (가안, ISS-014)
  { id: 'cB', name: '민원 재발', ratio: 20 },
];

const FACILITIES = [
  '횡단보도 앞',
  '버스정류장 앞',
  '초등학교 정문 앞',
  '시장 입구',
  '교차로 횡단보도',
  '어린이집 앞',
  '지하철역 출구 앞',
  '보행자 전용도로 입구',
  '근린공원 입구',
  '복지관 앞 횡단보도',
];
// 민원이 아닌 근거 지점(■). 모양은 하나뿐이고 종류는 말풍선 글자로 나눈다 (US-01 1-5, ISS-036)
const POINT_TYPES = [
  { key: 'accident', label: '보행자 사고 다발지' },
  { key: 'crosswalk', label: '횡단보도' },
  { key: 'busstop', label: '버스정류장' },
  { key: 'light', label: '보안등' },
];

// 민원 점(● 원본 좌표, ○ 근처 위치)에 붙는 보행 문제 유형 (가짜)
const COMPLAINT_TYPES = ['인도 불법 주정차', '횡단보도 불법 주정차', '보도 폭 부족', '조도 부족'];
const strHash = (s) => [...s].reduce((h, ch) => (Math.imul(h, 31) + ch.charCodeAt(0)) | 0, 7);

/**
 * 한 구역의 민원 점 (가짜). 기본 데이터의 난수와 따로 만들어 다른 값이 바뀌지 않게 한다.
 * - 같은 좌표의 민원은 한 점으로 묶고 count에 건수를 둔다 (예: 51)
 * - 몇 칸은 점이 300개를 넘게 만들어 묶음 표시(ISS-038)를 볼 수 있게 한다
 */
function buildComplaintPoints(c, isTop, order) {
  const r = mulberry32(strHash(c.gid) + 4242);
  const big = !isTop && order % 41 === 7;
  const mid = !isTop && !big && r() < 0.1;
  const n = isTop ? 24 : big ? 340 + Math.floor(r() * 260) : mid ? 60 + Math.floor(r() * 120) : 2 + Math.floor(r() * 18);
  const hot = Array.from({ length: 3 }, () => [(r() - 0.5) * 0.6, (r() - 0.5) * 0.6]);
  const spread = () => (r() + r() + r() - 1.5) * 0.18;
  return Array.from({ length: n }, (_, i) => {
    const uniform = r() < 0.3;
    const h = hot[Math.floor(r() * hot.length)];
    const dy = uniform ? r() - 0.5 : Math.max(-0.48, Math.min(0.48, h[0] + spread()));
    const dx = uniform ? r() - 0.5 : Math.max(-0.48, Math.min(0.48, h[1] + spread()));
    const near = r() < 0.06;
    let count = 1;
    if (near) count = 2 + Math.floor(r() * r() * 50); // 장소 이름으로 찾은 민원은 한 좌표에 겹친다
    else if (r() < 0.08) count = 2 + Math.floor(r() * 8);
    if (isTop && i === 0) count = 51;
    return {
      id: `${c.gid}-c${i}`,
      kind: 'complaint',
      near: isTop && i === 0 ? true : near,
      count,
      type: COMPLAINT_TYPES[Math.floor(r() * COMPLAINT_TYPES.length)],
      lat: c.lat + dy * D_LAT,
      lon: c.lon + dx * D_LON,
    };
  });
}
const POINT_ISSUES = {
  accident: ['보행자 사고 다발지 (N년 연속)', '보행자 사고 N건'],
  crosswalk: ['횡단보도 불법 주정차 민원 N건', '중간 대피 공간 없음', '보행 신호시간 판단 불가'],
  busstop: ['정류장 앞 인도 폭 부족', '인도 불법 주정차 민원 N건'],
  light: ['조도 부족 (2022년 측정)', '보도블럭 파손 민원 N건'],
};

/** 평가하지 못한 구역이 수집한 데이터와 못 한 데이터 (가짜). 모든 분야를 평가할 만큼 모이지 않은 구역이다. */
const COLLECT_POOL = [
  { name: '전국횡단보도표준데이터', value: (r) => `횡단보도 ${1 + Math.floor(r() * 3)}곳 (2025년 기준)` },
  { name: '보안등정보', value: (r) => `보안등 ${2 + Math.floor(r() * 6)}개 (2025년 기준)` },
  { name: '버스정류장 현황', value: (r) => `정류장 ${1 + Math.floor(r() * 2)}곳 (2025년 기준)` },
  { name: '행정동 인구', value: (r) => `격자 인구 ${20 + Math.floor(r() * 180)}명 (2025년 기준)` },
];
const MISSING_POOL = [
  { name: '보행자 사고 다발지', reason: '이 구역에 선정 기록 없음' },
  { name: '보도 폭(도면)', reason: '수치지형도에 보도 면이 없음' },
  { name: '조도·휘도', reason: '2022년 측정 구간 밖' },
  { name: '유동인구 (KT 추정)', reason: '행정동 단위만 있어 나눌 수 없음' },
  { name: '어린이·노인 이용 시설', reason: '구역 안에 위치 자료 없음' },
  { name: '주정차 민원', reason: '좌표 정확도 낮음으로 제외' },
];
const legalDong = (d) => d.replace(/\d+동$/, '동');
const pick = (r, arr) => arr[Math.floor(r() * arr.length)];

function shuffle(r, arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(r() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ---------------------------------------------------------------- 후보의 바뀌지 않는 부분
function buildBase() {
  const r = mulberry32(20261019);
  const cells = raw.cells.map(([gid, lat, lon, gu, dong]) => ({ gid, lat, lon, gu, dong }));

  // 평가하지 못한 구역(모든 분야를 평가하지 못함, D-04): 수정 5, 중원 4, 분당 5 = 14곳
  const unratedWant = { 수정구: 5, 중원구: 4, 분당구: 5 };
  const unratedSet = new Set();
  for (const gu of GU_LIST) {
    const ids = shuffle(
      r,
      cells.filter((c) => c.gu === gu).map((c) => c.gid),
    );
    // 맨 앞 후보(1위 예시)는 제외해 둔다
    ids.slice(0, unratedWant[gu]).forEach((id) => unratedSet.add(id));
  }

  // 1위 예시: 수정구 신흥동 2591 일대
  const topCell = cells.find((c) => c.gu === '수정구' && c.dong.startsWith('신흥') && !unratedSet.has(c.gid));
  unratedSet.delete(topCell.gid);

  const items = cells.map((c, cellIndex) => {
    const isTop = c.gid === topCell.gid;
    const dongL = legalDong(c.dong);
    const jibun = isTop ? 2591 : 100 + Math.floor(r() * 4900);
    const unratedAll = unratedSet.has(c.gid);

    // 근거 지점 3~6곳
    const nPoints = 3 + Math.floor(r() * 4);
    const points = Array.from({ length: nPoints }, (_, i) => {
      const t = POINT_TYPES[(i + Math.floor(r() * 4)) % POINT_TYPES.length];
      const issues = POINT_ISSUES[t.key];
      return {
        id: `${c.gid}-p${i}`,
        type: t.key,
        label: t.label,
        kind: 'site',
        // 지점에 마우스를 올리면 보이는 보행 문제 유형 (가짜 문구)
        issue: issues[Math.floor(r() * issues.length)].replace('N', String(1 + Math.floor(r() * 5))),
        lat: c.lat + (r() - 0.5) * D_LAT * 0.8,
        lon: c.lon + (r() - 0.5) * D_LON * 0.8,
      };
    });

    // 보행 방해요소: 1~4개
    let obKeys = isTop
      ? ['sidewalk', 'signal', 'light']
      : shuffle(r, OBSTACLES.map((o) => o.key)).slice(0, 1 + Math.floor(r() * 4));
    // 주정차 민원만으로 이루어진 후보가 생기지 않게, 민원 외 방해요소를 맨 앞에 하나 둔다
    if (!obKeys.some((k) => !k.startsWith('park'))) obKeys = ['sidewalk', ...obKeys];

    const landmark = isTop ? '신흥역 3번 출구 앞 횡단보도' : `${dongL} ${pick(r, FACILITIES)}`;
    const reliabilityRoll = r();
    const reliability = isTop ? '높음' : reliabilityRoll < 0.55 ? '높음' : reliabilityRoll < 0.85 ? '보통' : '낮음';

    // 이 후보에서 평가하지 못한 분야
    let collected = [];
    let missing = [];
    if (unratedAll) {
      const cs = shuffle(r, COLLECT_POOL).slice(0, 1 + Math.floor(r() * 2));
      collected = cs.map((x) => ({ name: x.name, value: x.value(r) }));
      missing = shuffle(r, MISSING_POOL).slice(0, 3 + Math.floor(r() * 3));
    }
    let unrated = [];
    if (unratedAll) {
      unrated = [
        { name: '사고', reason: '조사 안 함' },
        { name: '위험', reason: '조사 안 함' },
        { name: '노출', reason: '조사 안 함' },
        { name: '취약', reason: '조사 안 함' },
        { name: '연결성', reason: '공개 자료 없음' },
      ];
    } else if (!isTop) {
      const u = r();
      if (u < 0.22) unrated.push({ name: '연결성', reason: '공개 자료 없음' });
      else if (u < 0.34) unrated.push({ name: '보도 상태', reason: '조사 안 함' });
    }

    const roadRoll = r();
    const road = roadRoll < 0.72 ? '시도' : roadRoll < 0.82 ? '지방도' : roadRoll < 0.87 ? '국도' : '미확인';

    // 담당 부서 (F-01~F-04)
    const primary = OB[obKeys[0]];
    const dept = deptNameFor(primary.deptKind, c.gu);
    let deptStatus = null;
    if (dept) {
      const d = r();
      deptStatus = isTop ? '확인됨' : d < 0.78 ? '확인됨' : d < 0.93 ? '확인 필요' : '근거 없음';
    }

    return {
      gid: c.gid,
      gu: c.gu,
      dong: dongL,
      address: `${c.gu} ${dongL} ${jibun} 일대`,
      landmark,
      lat: c.lat,
      lon: c.lon,
      bounds: [
        [c.lat - D_LAT / 2, c.lon - D_LON / 2],
        [c.lat + D_LAT / 2, c.lon + D_LON / 2],
      ],
      points,
      complaintPoints: unratedAll ? [] : buildComplaintPoints(c, isTop, cellIndex),
      obstacles: obKeys,
      reliability,
      reliabilityReason:
        reliability === '높음'
          ? '근거 자료가 최근 기준일로 모두 갖춰져 있습니다'
          : reliability === '보통'
            ? '보도 상태 자료가 2022년 과거 기록입니다'
            : '조사하지 않은 분야가 있고 자료가 오래되었습니다',
      unrated,
      unratedAll,
      collected,
      missing,
      inProtectionZone: r() < 0.28,
      road,
      dept,
      deptStatus,
      complaintFlag: r() < 0.3 ? '재발 있음' : r() < 0.2 ? '시민 신고 단속 많음' : null,
    };
  });
  return { items, topId: topCell.gid };
}

// ---------------------------------------------------------------- 회차마다 달라지는 부분
function evidenceFor(base, rScore, complaint, run) {
  const r = mulberry32(base.gid.length * 7919 + Math.floor(rScore * 1000));
  const rows = [];
  const hasAccident = base.condA || r() < 0.4;
  if (hasAccident) {
    rows.push({
      field: '사고',
      item: '보행자 사고 다발지 선정',
      value: '3년 연속',
      short: '보행자 사고 다발지 3년 반복',
      pos: base.condA ? 2 : 4 + Math.floor(r() * 30),
      ratio: 30,
      basisYear: 2025,
      updateType: '연간',
      source: '도로교통공단 TAAS',
    });
  }
  base.obstacles.forEach((k) => {
    const o = OB[k];
    if (k === 'sidewalk') {
      const w = (1.2 + r() * 0.7).toFixed(1);
      rows.push({
        field: '위험',
        item: '보도 폭 2.0m 미만 구간(도면)',
        value: `${w}m`,
        short: '보도 폭 2.0m 미만 구간(도면)',
        pos: 3 + Math.floor(r() * 25),
        ratio: 25,
        basisYear: 2025,
        updateType: '연간',
        source: '국토지리정보원 수치지형도(2025)를 바탕으로 RADAR가 계산',
        sidewalkHelp: true,
      });
    } else if (k === 'signal') {
      rows.push({
        field: '위험',
        item: '횡단보도 보행 신호시간',
        value: '판단 불가',
        short: '보행 신호시간 판단 불가',
        pos: null,
        ratio: 25,
        basisYear: 2026,
        updateType: '1회성',
        source: '경찰서 회신 자료',
      });
    } else if (k === 'light') {
      rows.push({
        field: '위험',
        item: '횡단보도 주변 조도',
        value: '기준값 미만',
        short: '조도 부족(2022년 측정)',
        pos: 5 + Math.floor(r() * 30),
        ratio: 25,
        basisYear: 2022,
        updateType: '1회성',
        source: '성남시 도로 조도·휘도',
      });
    } else if (k === 'refuge') {
      rows.push({
        field: '위험',
        item: '횡단보도 중간 대피 공간',
        value: '없음',
        short: '중간 대피 공간 없음',
        pos: 6 + Math.floor(r() * 30),
        ratio: 25,
        basisYear: 2025,
        updateType: '연간',
        source: '전국횡단보도표준데이터(성남)',
      });
    } else if (o.deptKind === 'parking' && run.hasComplaints && complaint.total > 0) {
      rows.push({
        field: '위험',
        item: '주정차 위반 단속',
        value: `${complaint.total}건`,
        short: `주정차 단속 ${complaint.total}건`,
        pos: 6 + Math.floor(r() * 30),
        ratio: 25,
        basisYear: 2026,
        updateType: '반기',
        source: '성남시 주정차 위반 단속 위치 현황',
      });
    }
  });
  rows.push({
    field: '노출',
    item: '유동인구 (KT 추정, 보행량 아님)',
    value: '상위 구간',
    short: `횡단보도 ${3 + Math.floor(r() * 6)}곳`,
    pos: 8 + Math.floor(r() * 30),
    ratio: 25,
    basisYear: 2025,
    updateType: '반기',
    source: '경기도 KT 추정 유동인구',
  });
  rows.push({
    field: '취약',
    item: '어린이·노인 이용 시설',
    value: `${1 + Math.floor(r() * 5)}곳`,
    short: '어린이·노인 이용 시설 인접',
    pos: 10 + Math.floor(r() * 35),
    ratio: 20,
    basisYear: 2025,
    updateType: '연간',
    source: '유치원알리미·경기도',
  });
  return rows.filter((row) => !base.unratedAll && !base.unrated.some((u) => u.name === row.field));
}

function explanationFor(base, evidence) {
  const accident = evidence.find((e) => e.field === '사고');
  if (accident) {
    return '이 구역은 2023~2025년 보행자 사고 다발지에 3년 연속 선정되었습니다(2025년 기준).';
  }
  const sw = evidence.find((e) => e.sidewalkHelp);
  if (sw) {
    return `이 구역은 도면에서 잰 보도 폭이 ${sw.value}인 구간이 있습니다(2025년 기준).`;
  }
  const first = evidence[0];
  if (first && first.field === '위험') {
    return `이 구역은 ${first.item} 자료가 확인됩니다(${first.basisYear}년 기준).`;
  }
  return '이 구역은 근거 지점이 모여 있어 먼저 확인할 만합니다(2025년 기준).';
}

function articlesFor(base, rScore) {
  const list = [];
  const keys = base.obstacles;
  if (keys.includes('sidewalk')) {
    list.push({
      id: 'a-sidewalk',
      name: '보도 설치 및 관리 지침 3.2 (유효 보도 폭)',
      effective: '2022.11.07',
      pending: false,
    });
    if (rScore > 70) {
      list.push({
        id: 'a-sidewalk-next',
        name: '보도 설치 및 관리 지침 3.2 (개정안)',
        effective: '2027.03.01',
        pending: true, // 시행 전 조문은 '시행 전' 꼬리표로 따로 둔다 (E-04)
      });
    }
  }
  if (keys.includes('parkSidewalk') || keys.includes('parkCross')) {
    list.push({
      id: 'a-park',
      name: '도로교통법 제32조 (정차 및 주차의 금지)',
      effective: '2024.07.01',
      pending: false,
    });
  }
  return list.map((a) => ({
    ...a,
    body: '[가안] 이 자리에 법령 원문 문단이 들어갑니다. 조·항·호 단위로 나누고 시행일을 붙입니다.',
  }));
}

function complaintFor(base, r) {
  const t1 = Math.floor(r() * 5);
  const t2 = Math.floor(r() * 3);
  const recur1 = Math.min(t1, Math.floor(r() * 3));
  const recur2 = Math.min(t2, Math.floor(r() * 2));
  const types = [];
  if (t1) types.push({ type: '인도 불법 주정차', count: t1, recur: recur1 });
  if (t2) types.push({ type: '횡단보도 불법 주정차', count: t2, recur: recur2 });
  return {
    total: t1 + t2,
    recur: recur1 + recur2,
    types,
    lowAccuracy: r() < 0.12 ? 1 : 0, // 위치가 정확하지 않아 세지 않은 민원 (ISS-033)
  };
}

/** 회차 하나의 후보 목록 */
function buildRunItems(runId, bases, prev) {
  const run = RUNS.find((x) => x.id === runId);
  const seed = { r2026: 26001, r2026h2: 26002, r2027: 27001, r2028: 28001 }[runId];
  const r = mulberry32(seed);

  // 점수 (0~100). 1위는 수정구 신흥동 예시(87)
  const items = bases.map((b) => {
    const prevScore = prev ? prev.find((p) => p.gid === b.gid)?.score : null;
    let score;
    if (b.unratedAll) score = null;
    else if (prevScore != null) score = Math.max(20, Math.min(92, prevScore + (r() - 0.5) * 18));
    else score = 28 + r() * 58;
    return { b, score };
  });
  items.forEach((it) => {
    if (it.score != null && it.b.gid === bases.topId) it.score = 87;
    else if (it.score != null && it.score >= 86.5) it.score = 86.4 - r();
    if (it.score != null) it.score = Math.round(it.score * 10) / 10;
  });

  // 우선 확인 조건: 수정 3, 중원 2, 분당 3
  const condWant = { 수정구: 3, 중원구: 2, 분당구: 3 };
  const condMap = {};
  for (const gu of GU_LIST) {
    const pool = items
      .filter((it) => it.b.gu === gu && it.score != null)
      .sort((a, c) => c.score - a.score);
    const chosen = [];
    if (gu === '수정구') chosen.push(pool.find((p) => p.b.gid === bases.topId));
    for (const p of pool) {
      if (chosen.length >= condWant[gu]) break;
      if (!chosen.includes(p)) chosen.push(p);
    }
    chosen.forEach((p, i) => {
      const ids = ['cA'];
      if (run.hasComplaints && i === 1) ids.push('cB'); // 둘째 후보는 두 조건에 모두 맞음
      if (run.hasComplaints && i === 2) ids.splice(0, 1, 'cB');
      condMap[p.b.gid] = ids;
    });
  }

  return items.map(({ b, score }, idx) => {
    const cr = mulberry32(b.gid.charCodeAt(b.gid.length - 1) * 31 + b.gid.length * 977 + seed);
    const complaint = run.hasComplaints ? complaintFor(b, cr) : { total: 0, recur: 0, types: [], lowAccuracy: 0 };
    const baseWithCond = { ...b, condA: (condMap[b.gid] || []).includes('cA') };
    const evidence = score == null ? [] : evidenceFor(baseWithCond, score, complaint, run);
    const explanation = score == null ? null : explanationFor(baseWithCond, evidence);
    return {
      gid: b.gid,
      score,
      conditions: condMap[b.gid] || [],
      complaint,
      evidence,
      explanation: score != null && idx % 53 === 17 ? null : explanation, // 설명문을 만들지 못한 예 (US-02 9)
      articles: score == null ? [] : articlesFor(b, score),
      decision: DECISION.NONE,
      reasonKey: null,
      reasonText: null,
      memo: null,
      history: [],
    };
  });
}

function assignDecisions(items, bases, wanted, dateSeed, orgOf, firstFree) {
  // wanted: { 구: { 우선: n, 제외: n, 보류: n } } 점수가 높은 후보에서 섞어 배정한다.
  const r = mulberry32(dateSeed);
  for (const gu of GU_LIST) {
    const pool = items
      .filter((it) => bases.find((b) => b.gid === it.gid).gu === gu && it.score != null)
      .sort((a, c) => c.score - a.score)
      .filter((it) => it.gid !== firstFree);
    const slots = [];
    const w = wanted[gu];
    for (let i = 0; i < w.target; i++) slots.push(DECISION.TARGET);
    for (let i = 0; i < w.exclude; i++) slots.push(DECISION.EXCLUDE);
    for (let i = 0; i < w.hold; i++) slots.push(DECISION.HOLD);
    const order = pool.slice(0, Math.floor(pool.length * 0.55));
    const chosen = shuffle(r, order).slice(0, slots.length);
    chosen.forEach((it, i) => {
      const decision = slots[i];
      it.decision = decision;
      if (decision === DECISION.TARGET) {
        it.reasonKey = null;
        it.reasonText = null;
      } else {
        it.reasonKey = pick(r, DECISION_REASONS.slice(0, 4));
        it.reasonText = it.reasonKey;
        it.memo = r() < 0.4 ? '내년 재검토' : null;
      }
      const day = String(1 + Math.floor(r() * 28)).padStart(2, '0');
      it.history = [
        {
          date: wanted.year === 2027 ? `2026.11.${day}` : `2025.12.${day}`,
          from: DECISION.NONE,
          to: decision,
          org: orgOf(gu),
        },
      ];
    });
  }
}

function build() {
  const { items: bases, topId } = buildBase();
  bases.topId = topId;
  const orgOf = (gu) => `${gu} 건설과 도로관리팀`;

  // 2026 연간 (확정): 작년 결정으로 쓴다
  const i2026 = buildRunItems('r2026', bases, null);
  assignDecisions(
    i2026,
    bases,
    {
      year: 2026,
      수정구: { target: 20, exclude: 8, hold: 7 },
      중원구: { target: 18, exclude: 6, hold: 6 },
      분당구: { target: 19, exclude: 7, hold: 6 },
    },
    777,
    orgOf,
    topId,
  );

  // 2026 하반기 참고: 바뀐 자료로 다시 계산한 순위. 결정은 2026 연간 그대로(확정 대상은 바뀌지 않는다).
  const i2026h2 = buildRunItems('r2026h2', bases, i2026);
  i2026h2.forEach((it) => {
    const src = i2026.find((x) => x.gid === it.gid);
    it.decision = src.decision;
    it.reasonKey = src.reasonKey;
    it.reasonText = src.reasonText;
    it.memo = src.memo;
    it.history = src.history;
  });

  // 2027 연간 (검토 중): 구별 시작 숫자는 명세 예시와 같게 맞춘다 (US-01 1-1)
  const i2027 = buildRunItems('r2027', bases, i2026);
  assignDecisions(
    i2027,
    bases,
    {
      year: 2027,
      수정구: { target: 21, exclude: 9, hold: 6 },
      중원구: { target: 20, exclude: 6, hold: 4 },
      분당구: { target: 17, exclude: 6, hold: 7 },
    },
    4242,
    orgOf,
    topId,
  );

  // 작년 결정(④ 탭): 2026 연간에서 결정한 곳만
  i2027.forEach((it) => {
    const prev = i2026.find((x) => x.gid === it.gid);
    it.lastYear =
      prev && prev.decision !== DECISION.NONE
        ? {
            runName: '2026 연간',
            decision: prev.decision,
            reason: prev.reasonText,
            memo: prev.memo,
          }
        : null;
  });
  // 명세 예시: 작년 보류(예산·공정 사정 / 내년 재검토)
  const ex = i2027.find((it) => it.lastYear && it.lastYear.decision === DECISION.HOLD);
  if (ex) ex.lastYear = { runName: '2026 연간', decision: DECISION.HOLD, reason: '예산·공정 사정', memo: '내년 재검토' };

  // 2028 연간 (산정 중): 사용자 화면에는 보이지 않는다
  const i2028 = buildRunItems('r2028', bases, i2027);

  return {
    bases,
    topId,
    byRun: { r2027: i2027, r2026h2: i2026h2, r2026: i2026, r2028: i2028 },
    boundaries: raw.boundaries,
  };
}

export const DATASET = build();

/** 초기 구 확정 상태 */
export const INITIAL_GU_CONFIRM = {
  r2027: { 수정구: null, 중원구: '2026-12-08', 분당구: null }, // US-04 예시: 중원구 확정 완료 2026.12.08
  r2026: { 수정구: '2026-02-05', 중원구: '2026-02-06', 분당구: '2026-02-04' },
  r2026h2: { 수정구: '2026-02-05', 중원구: '2026-02-06', 분당구: '2026-02-04' },
  r2028: { 수정구: null, 중원구: null, 분당구: null },
};

export { OB };
