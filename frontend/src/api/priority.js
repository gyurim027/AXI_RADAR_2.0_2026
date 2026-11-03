// 점수·순위 모델(/api/priority, 진규)의 응답을 사용자 화면이 쓰는 모양으로 바꾼다.
// 서버에 없는 값은 가짜로 채우지 않고 비워 둔다(null·빈 목록). 화면은 비어 있으면 '-'나 안내를 보인다.
// 서버에 값이 생기면(회차 상태·주소·담당 부서 등) 이 파일만 고치면 된다. 문서: 작업파일/261103/배포준비_빠진기능_점검.
import { DECISION, RUN_STATUS } from '../shared/constants.js';
import { snakeKeys } from './caseKeys.js';

// 보존 대상 회차(기존 1회차). 서버가 목록에서 거르면 이 줄을 지운다 (결정 기록 D-46).
const PRESERVED_RUN_IDS = new Set([1]);

// 격자 한 칸은 250m다 (DB 01_grid_cell 이웃 중심 간격: 위도 0.0022535°, 경도 0.002825°).
// 서버가 경계를 주지 않아, 중심에서 반 칸씩 떨어진 사각형으로 칸을 그린다.
const HALF_LAT = 0.0022535 / 2;
const HALF_LON = 0.002825 / 2;
export function cellBounds(lat, lon) {
  return [
    [lat - HALF_LAT, lon - HALF_LON],
    [lat + HALF_LAT, lon + HALF_LON],
  ];
}

// 점수 모델 지표 9개 → 화면 이름·분야 (우선순위 로직 문서 5호, 2026-10-28)
export const INDICATORS = {
  res_fatal_accident_cnt: { name: '사망 사고', domain: 'accident' },
  res_hotspot_cnt: { name: '사고 다발지', domain: 'accident' },
  res_ped_hotspot_cnt: { name: '보행자 사고 다발지', domain: 'accident' },
  cond_blind_spot_cnt: { name: '사각지대', domain: 'hazard' },
  cond_obstacle_cnt: { name: '보행 장애물', domain: 'hazard' },
  cond_pothole_detect_cnt: { name: '포트홀', domain: 'hazard' },
  cond_delineator_detect_cnt: { name: '시선유도시설', domain: 'hazard' },
  exp_board_alight_daily_avg: { name: '대중교통 이용', domain: 'exposure' },
  vul_zone_total: { name: '보호구역 등', domain: 'vulnerability' },
};
export const DOMAIN_LABEL = { accident: '사고', hazard: '위험', exposure: '노출', vulnerability: '취약' };
const RELIABILITY = { HIGH: '높음', MEDIUM: '보통', LOW: '낮음' };
const UNEVALUATED = { OUTSIDE_SURVEY_SCOPE: '조사 안 함', NO_RECORD_COVERAGE_UNKNOWN: '기록 없음' };
// 우선 확인 조건: 점수 모델은 위험·노출·취약 세 분야로 판정한다. 화면 이름은 기획에서 정하기 전까지 분야 이름을 쓴다.
export const PRIORITY_CONDITIONS = [
  { id: 'hazard', name: '위험 조건', ratio: null },
  { id: 'exposure', name: '노출 조건', ratio: null },
  { id: 'vulnerability', name: '취약 조건', ratio: null },
];
const STATUS_VALUES = new Set(Object.values(RUN_STATUS));
const num = (v) => (v == null ? null : Number(v));
const round1 = (v) => Math.round(Number(v) * 10) / 10; // 점수는 소수 첫째 자리까지 보인다(순서는 서버 원래 값으로 매긴다)

/** 서버 회차 한 건 → 화면 회차. 상태·이름·종류가 서버에 없으면 '상태 정보 없음'·'회차 N'으로 둔다(가짜 상태를 만들지 않는다). */
export function toRun(r) {
  const id = String(r.run_id);
  const status = STATUS_VALUES.has(r.status) ? r.status : RUN_STATUS.UNKNOWN;
  return {
    id,
    name: r.name || `회차 ${r.run_id}`,
    kind: r.kind === '반기 참고' ? 'ref' : 'annual',
    status,
    openedAt: r.opened_at ?? null,
    dataRange: null,
    version: r.setting_version_display || null,
    unratedFields: [],
    hasComplaints: null,
    complaintPeriod: null,
    conditionCount: PRIORITY_CONDITIONS.length,
    dataCount: null,
  };
}

const percentLabel = (rank, total) => Math.max(1, Math.ceil((rank / total) * 100));

function splitDomains(details) {
  const reasons = details?.unevaluated_reasons && !Array.isArray(details.unevaluated_reasons) ? details.unevaluated_reasons : {};
  const contributions = details?.indicator_contributions || {};
  const unrated = [];
  Object.keys(DOMAIN_LABEL).forEach((domain) => {
    const codes = Object.keys(INDICATORS).filter((c) => INDICATORS[c].domain === domain);
    if (codes.length && codes.every((c) => reasons[c])) {
      unrated.push({ name: DOMAIN_LABEL[domain], reason: UNEVALUATED[reasons[codes[0]]] || '기록 없음' });
    }
  });
  // 보행 방해요소: 위험 분야 지표 중 점수에 기여한 것을 기여가 큰 순서로
  const obstacles = Object.keys(INDICATORS)
    .filter((c) => INDICATORS[c].domain === 'hazard' && Number(contributions[c]) > 0)
    .sort((a, b) => Number(contributions[b]) - Number(contributions[a]))
    .map((c) => INDICATORS[c].name);
  return { unrated, obstacles };
}

function toRow(c, rank, scopeTotal, cityRank, cityTotal) {
  const rated = c.score != null;
  const tierRatio = rated ? rank / scopeTotal : 1;
  const tier = !rated ? 'unrated' : tierRatio <= 0.1 ? 'top' : tierRatio <= 0.3 ? 'mid' : 'rest';
  const { unrated, obstacles } = splitDomains(c.details);
  const matched = String(c.matched_roles || '').split(',').filter(Boolean);
  const hasCenter = c.center_lat != null && c.center_lon != null;
  return {
    gid: c.gid,
    rank: rated ? rank : null,
    gu: c.gu || null,
    address: null, // 서버 응답에 없음(대환님 요청 중)
    landmark: null,
    score: rated ? round1(c.score) : null,
    tier,
    obstacleMain: obstacles[0] || '-',
    obstacleRest: Math.max(0, obstacles.length - 1),
    obstacleNames: obstacles,
    reliability: RELIABILITY[c.details?.confidence_grade] || null,
    unratedCount: unrated.length,
    unratedAll: unrated.length === Object.keys(DOMAIN_LABEL).length,
    unratedNames: unrated.map((u) => u.name),
    notSurveyed: unrated.filter((u) => u.reason === '조사 안 함').map((u) => u.name),
    collected: [],
    missing: [],
    decision: DECISION.NONE, // 결정 목록 API가 서버에 없어 전부 '결정 전'으로 보인다
    conditions: matched,
    inProtectionZone: false,
    complaintFlag: null,
    recur: false,
    bounds: hasCenter ? cellBounds(num(c.center_lat), num(c.center_lon)) : null,
    points: [],
    complaintPoints: [],
    cityPercent: rated && cityRank ? percentLabel(cityRank, cityTotal) : null,
    _server: { rankNo: c.rank_no ?? null, complaintCnt: c.complaint_cnt ?? null },
  };
}

/** 후보 목록 응답 → 화면 목록 */
export function toCandidateList(res, user, { gu, guList, allGu }) {
  const run = toRun(res.run);
  const all = res.candidates || [];
  const rated = all.filter((c) => c.score != null).sort((a, b) => Number(b.score) - Number(a.score) || (a.rank_no ?? 1e9) - (b.rank_no ?? 1e9));
  const unratedList = all.filter((c) => c.score == null);
  const cityTotal = rated.length;
  const rows = rated.map((c, i) => toRow(c, i + 1, cityTotal, c.rank_no || i + 1, cityTotal));
  const unrated = unratedList.map((c) => toRow(c, 0, cityTotal, 0, cityTotal));
  const wantGus = user.role === 'district' ? [user.gu] : gu && gu !== allGu ? [gu] : guList;
  // 구 안 순위는 보이는 범위(구 도로관리팀은 자기 구) 안에서 다시 매긴다
  const inScope = rows.filter((r) => r.gu && wantGus.includes(r.gu)).map((r, i, arr) => ({ ...r, rank: i + 1, tier: tierOf(i + 1, arr.length) }));
  const counts = { total: inScope.length, none: inScope.length, target: 0, exclude: 0, hold: 0 };
  return {
    run,
    guScope: user.role === 'district' ? user.gu : gu || allGu,
    items: inScope,
    unrated: unrated.filter((r) => r.gu && wantGus.includes(r.gu)),
    counts,
    conditions: PRIORITY_CONDITIONS,
    guBoundaries: [],
    obstacleOptions: Object.values(INDICATORS).filter((i) => i.domain === 'hazard').map((i) => i.name),
    myConfirm: null,
    canDecide: false,
    _all: all,
  };
}

function tierOf(rank, total) {
  const r = rank / total;
  return r <= 0.1 ? 'top' : r <= 0.3 ? 'mid' : 'rest';
}

/** 후보 상세 응답 → 화면 상세. 중심 좌표는 상세에 없어 목록에서 받은 값을 쓴다. */
export function toCandidateDetail(c, { list, user }) {
  const row = list?.items?.find((r) => r.gid === c.gid) || list?.unrated?.find((r) => r.gid === c.gid) || null;
  const d = c.details || {};
  const contributions = d.indicator_contributions || {};
  const total = Object.values(contributions).reduce((s, v) => s + (Number(v) > 0 ? Number(v) : 0), 0);
  const evidence = Object.keys(INDICATORS)
    .filter((code) => contributions[code] != null)
    .sort((a, b) => Number(contributions[b]) - Number(contributions[a]))
    .map((code) => ({
      field: DOMAIN_LABEL[INDICATORS[code].domain],
      item: INDICATORS[code].name,
      value: `기여 ${Number(contributions[code]).toFixed(1)}점`,
      pos: null,
      ratio: total ? Math.round((Number(contributions[code]) / total) * 100) : 0,
      basisYear: null,
      updateType: null,
      source: '점수 모델 저장 결과',
      sidewalkHelp: false,
    }));
  const { unrated, obstacles } = splitDomains(d);
  const summary = c.explanation_context?.summary;
  const conditions = String(c.matched_roles || '').split(',').filter(Boolean).map((id) => PRIORITY_CONDITIONS.find((p) => p.id === id)).filter(Boolean);
  const dept = c.department && c.department.name ? { name: c.department.name, contact: null, status: c.department.confidence || null } : null;
  return {
    run: list?.run || null,
    gid: c.gid,
    rank: row?.rank ?? null,
    cityRank: c.rank_no ?? null,
    cityPercent: row?.cityPercent ?? null,
    gu: c.gu || null,
    address: null,
    landmark: null,
    score: c.score != null ? round1(c.score) : null,
    decision: DECISION.NONE,
    explanation: typeof summary === 'string' ? summary : '',
    evidence,
    topEvidence: evidence.slice(0, 3).map((e) => `${e.item} ${e.value}`),
    axes: [...new Set(evidence.map((e) => e.field))].slice(0, 3),
    reliability: RELIABILITY[d.confidence_grade] || null,
    reliabilityReason: '',
    conditions,
    unrated,
    obstacles,
    complaint: { has: c.complaint_cnt != null, total: c.complaint_cnt ?? 0, types: [], recur: 0 },
    articles: [],
    dept,
    deptReason: c.department?.reason || '',
    deptOptions: [],
    lastYear: null,
    history: [],
    reasonText: '',
    memo: '',
    bounds: row?.bounds || null,
    points: [],
    canDecide: false,
    showDecisionTab: false,
    canPickDept: false,
    showRequest: false,
    confirmedByGu: false,
    problems: [],
    request: null,
    org: user?.org || '',
  };
}

export function createPriorityApi(rawRequest) {
  const request = async (path, options) => snakeKeys(await rawRequest(path, options));
  let lastList = null;
  return {
    /** 회차 목록. 보존 대상 회차는 뺀다. */
    async listRuns() {
      const d = await request('/api/priority/runs');
      return (d.runs || []).filter((r) => !PRESERVED_RUN_IDS.has(Number(r.run_id))).map(toRun);
    },
    async listCandidates({ runId, gu, user, guList, allGu }) {
      const res = await request(`/api/priority/runs/${encodeURIComponent(runId)}/candidates?limit=3000`);
      lastList = toCandidateList(res, user, { gu, guList, allGu });
      return lastList;
    },
    async getCandidateDetail({ runId, gid, user }) {
      const c = await request(`/api/priority/runs/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(gid)}`);
      return toCandidateDetail(c, { list: lastList, user });
    },
  };
}
