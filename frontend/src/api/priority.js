// 점수·순위 모델(/api/priority, 진규)의 응답을 사용자 화면이 쓰는 모양으로 바꾼다.
// 서버에 없는 값은 가짜로 채우지 않고 비워 둔다(null·빈 목록). 화면은 비어 있으면 '-'나 안내를 보인다.
// 서버에 값이 생기면(회차 상태·주소·담당 부서 등) 이 파일만 고치면 된다. 문서: 작업파일/261103/배포준비_빠진기능_점검.
import { DECISION, RUN_STATUS } from '../shared/constants.js';
import { snakeKeys } from './caseKeys.js';
import { toLocation } from './locationLabel.js';

// 기존 1회차는 보존 대상이다(진규님 확정 2026-11-03). 서버는 조회를 유지하고 신규 결정·확정을 거절한다.
// 일반 사용자 화면과 시연에서는 제외한다. 기본은 2회차이며, 2회차를 못 불러와도 1회차로 자동 전환하지 않는다.
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
// name은 목록의 '주요 보행 방해요소'에 쓰는 짧은 이름, label은 근거 표의 정식 표시 이름이다(진규님 최종 표시 기준, 공용 DB grid_feature 컬럼 설명과 대조).
export const INDICATORS = {
  res_fatal_accident_cnt: { name: '사망사고', label: '격자 내 사망사고 건수', domain: 'accident' },
  res_hotspot_cnt: { name: '사고다발지', label: '격자와 겹치는 사고다발지 자료 행 수', domain: 'accident' },
  res_ped_hotspot_cnt: { name: '보행자 사고다발지', label: '보행자 사망·중상 다발지 지점 수', domain: 'accident' },
  cond_blind_spot_cnt: { name: '사각지대', label: '우회전 사각지대 수', domain: 'hazard' },
  cond_obstacle_cnt: { name: '보행 방해물', label: '적치물 등 보행 장애물 수', domain: 'hazard' },
  cond_pothole_detect_cnt: { name: '포트홀', label: '포트홀 탐지 건수', domain: 'hazard' },
  cond_delineator_detect_cnt: { name: '시선유도시설', label: '파손 시선유도봉 탐지 건수', domain: 'hazard' },
  exp_board_alight_daily_avg: { name: '승하차량', label: '격자 내 정류소 일평균 승하차량 합계(보행량 대체 지표)', domain: 'exposure' },
  vul_zone_total: { name: '보호구역', label: '격자와 겹치는 보호구역 수', domain: 'vulnerability' },
};
export const DOMAIN_LABEL = { accident: '사고', hazard: '위험', exposure: '노출', vulnerability: '취약' };
const RELIABILITY = { HIGH: '높음', MEDIUM: '보통', LOW: '낮음' };
// 미평가 사유는 위험이 없다는 뜻이 아니다. 0점으로 처리하지 않는다(진규님 2026-11-03).
const UNEVALUATED = {
  OUTSIDE_SURVEY_SCOPE: '장애물 조사 범위 밖',
  NO_RECORD_COVERAGE_UNKNOWN: '탐지 기록이 없고 관측 범위를 확인할 수 없음',
};
// 우선 확인 조건은 종합·위험·노출·취약 4개다(진규님 확인). 값은 Y(충족)·N(미충족)·NULL(미평가)이고, NULL을 N으로 바꾸지 않는다.
// 종합이 Y인 후보가 '우선 확인 조건에 맞는 후보'다. 조건 충족 여부는 후보 선정 여부와 다른 값이다.
export const PRIORITY_CONDITIONS = [
  { id: 'result', name: '종합 조건', ratio: null },
  { id: 'hazard', name: '위험 조건', ratio: null },
  { id: 'exposure', name: '노출 조건', ratio: null },
  { id: 'vulnerable', name: '취약 조건', ratio: null },
];
const conditionValue = (v) => (v === 'Y' || v === 'N' ? v : v == null ? 'NULL' : 'INVALID');
/** 후보의 조건 4개 상태. 화면은 NULL을 '미평가'로 보인다. */
export function conditionStates(conditions) {
  return PRIORITY_CONDITIONS.map((c) => ({ id: c.id, name: c.name, state: conditionValue(conditions?.[c.id]) }));
}
/** 우선 확인 조건에 맞는 후보(종합 Y)의 맞은 조건 번호. 맞지 않으면 빈 목록이다. */
function matchedConditionIds(conditions) {
  if (conditionValue(conditions?.result) !== 'Y') return [];
  return PRIORITY_CONDITIONS.filter((c) => conditionValue(conditions?.[c.id]) === 'Y').map((c) => c.id);
}
const STATUS_VALUES = new Set(Object.values(RUN_STATUS));
const DECISION_VALUES = new Set([DECISION.TARGET, DECISION.EXCLUDE, DECISION.HOLD]);
const num = (v) => (v == null ? null : Number(v));
const round1 = (v) => Math.round(Number(v) * 10) / 10; // 점수는 소수 첫째 자리까지 보인다(순서는 서버 원래 값으로 매긴다)

/** 서버 회차 한 건 → 화면 회차. 상태·이름·종류가 서버에 없으면 '상태 정보 없음'·'회차 N'으로 둔다(가짜 상태를 만들지 않는다). */
export function toRun(r, { finalized = false } = {}) {
  const id = String(r.run_id);
  let status = STATUS_VALUES.has(r.status) ? r.status : RUN_STATUS.UNKNOWN;
  // 서버가 상태를 주지 않을 때, 3개 구가 모두 확정했다는 서버 값(round_finalized)이 있으면 '확정'으로 본다.
  if (status === RUN_STATUS.UNKNOWN && finalized) status = RUN_STATUS.FINAL;
  // 개발 전용: 로컬에서 결정·확정 화면을 시험하려고 상태를 덮어쓴다. 개발 서버(DEV)에서만 읽고 배포 빌드에서는 무시한다.
  const devStatus = import.meta.env?.DEV ? import.meta.env?.VITE_DEV_RUN_STATUS : null;
  if (status === RUN_STATUS.UNKNOWN && STATUS_VALUES.has(devStatus)) status = devStatus;
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

/** 어드민 회차 목록의 한 줄. 서버가 주지 않는 값(생성일·검토 시작일·민원 기간)은 '-'로 두고 가짜로 채우지 않는다. */
export function toAdminRun(run) {
  return {
    id: run.id,
    name: run.name,
    kind: run.kind === 'ref' ? '반기 참고' : '연간',
    kindLabel: run.kind === 'ref' ? '반기 참고' : '연간',
    status: run.status,
    version: run.version || '-',
    created: '-',
    review: run.openedAt ? String(run.openedAt).slice(0, 10).replaceAll('-', '.') : '-',
    period: '-',
    complaintPeriod: null,
    calcDone: false,
    ran: false,
    running: false,
    unratedFields: [],
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
  const hasCenter = c.center_lat != null && c.center_lon != null;
  return {
    gid: c.gid,
    rank: rated ? rank : null,
    gu: c.gu || null,
    ...toLocation(c), // 주소·대표 지점은 같은 격자에 연결된 시설 자료의 참고 값이다(D-59). 없으면 null
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
    conditions: matchedConditionIds(c.conditions),
    conditionStates: conditionStates(c.conditions),
    inProtectionZone: false,
    complaintFlag: null,
    recur: false,
    bounds: hasCenter ? cellBounds(num(c.center_lat), num(c.center_lon)) : null,
    points: null, // 서버가 근거 지점을 주지 않으면 0곳이 아니라 모르는 값이다(null)
    complaintPoints: null,
    cityPercent: rated && cityRank ? percentLabel(cityRank, cityTotal) : null,
    _server: { rankNo: c.rank_no ?? null, complaintCnt: c.complaint_cnt ?? null },
  };
}

/** 후보 목록 응답 → 화면 목록 */
export function toCandidateList(res, user, { gu, guList, allGu, decisions = null, myConfirm = null, finalized = false }) {
  const run = toRun(res.run, { finalized });
  const all = res.candidates || [];
  const rated = all.filter((c) => c.score != null).sort((a, b) => Number(b.score) - Number(a.score) || (a.rank_no ?? 1e9) - (b.rank_no ?? 1e9));
  const unratedList = all.filter((c) => c.score == null);
  const cityTotal = rated.length;
  const rows = rated.map((c, i) => toRow(c, i + 1, cityTotal, c.rank_no || i + 1, cityTotal));
  const unrated = unratedList.map((c) => toRow(c, 0, cityTotal, 0, cityTotal));
  const wantGus = user.role === 'district' ? [user.gu] : gu && gu !== allGu ? [gu] : guList;
  // 구 안 순위는 보이는 범위(구 도로관리팀은 자기 구) 안에서 다시 매긴다
  const inScope = rows.filter((r) => r.gu && wantGus.includes(r.gu)).map((r, i, arr) => ({ ...r, rank: i + 1, tier: tierOf(i + 1, arr.length) }));
  // 결정 목록(G-03)이 없으면(null) 서버가 결정을 주지 않은 것이라 전부 '결정 전'으로 둔다.
  const byGid = new Map((decisions || []).map((d) => [d.gid, d]));
  inScope.forEach((r) => {
    const d = byGid.get(r.gid);
    if (d && DECISION_VALUES.has(d.decision)) r.decision = d.decision;
  });
  const counts = { total: inScope.length, none: 0, target: 0, exclude: 0, hold: 0 };
  inScope.forEach((r) => {
    if (r.decision === DECISION.TARGET) counts.target++;
    else if (r.decision === DECISION.EXCLUDE) counts.exclude++;
    else if (r.decision === DECISION.HOLD) counts.hold++;
    else counts.none++;
  });
  const reviewing = run.status === RUN_STATUS.REVIEW;
  return {
    run,
    guScope: user.role === 'district' ? user.gu : gu || allGu,
    items: inScope,
    unrated: unrated.filter((r) => r.gu && wantGus.includes(r.gu)),
    counts,
    conditions: PRIORITY_CONDITIONS,
    guBoundaries: [],
    // 서버가 값을 주지 않아 걸러도 항상 0건이 되는 필터. 없애지 않고 막아 둔다.
    unavailableFilters: ['zone', 'complaint'],
    obstacleOptions: Object.values(INDICATORS).filter((i) => i.domain === 'hazard').map((i) => i.name),
    myConfirm: user.role === 'district' ? myConfirm : null,
    // 결정 버튼: 구 도로관리팀 · 검토 중 회차 · 자기 구를 아직 확정하기 전 (CM-00 10번)
    canDecide: user.role === 'district' && !user.readOnly && reviewing && !!myConfirm && !myConfirm.done,
    _all: all,
  };
}

function tierOf(rank, total) {
  const r = rank / total;
  return r <= 0.1 ? 'top' : r <= 0.3 ? 'mid' : 'rest';
}

/** 후보 상세 응답 → 화면 상세. 중심 좌표는 상세에 없어 목록에서 받은 값을 쓴다. */
export function toCandidateDetail(c, { list, user, record = null }) {
  const row = list?.items?.find((r) => r.gid === c.gid) || list?.unrated?.find((r) => r.gid === c.gid) || null;
  const d = c.details || {};
  const contributions = d.indicator_contributions || {};
  const total = Object.values(contributions).reduce((s, v) => s + (Number(v) > 0 ? Number(v) : 0), 0);
  const evidence = Object.keys(INDICATORS)
    .filter((code) => contributions[code] != null)
    .sort((a, b) => Number(contributions[b]) - Number(contributions[a]))
    .map((code) => ({
      field: DOMAIN_LABEL[INDICATORS[code].domain],
      item: INDICATORS[code].label,
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
  const conditions = matchedConditionIds(c.conditions).map((id) => PRIORITY_CONDITIONS.find((p) => p.id === id)).filter(Boolean);
  const dept = c.department && c.department.name ? { name: c.department.name, contact: null, status: c.department.confidence || null } : null;
  return {
    run: list?.run || null,
    gid: c.gid,
    rank: row?.rank ?? null,
    cityRank: c.rank_no ?? null,
    cityPercent: row?.cityPercent ?? null,
    gu: c.gu || null,
    ...toLocation(c),
    score: c.score != null ? round1(c.score) : null,
    decision: record && DECISION_VALUES.has(record.decision) ? record.decision : DECISION.NONE,
    explanation: typeof summary === 'string' ? summary : '',
    evidence,
    topEvidence: evidence.slice(0, 3).map((e) => `${e.item} ${e.value}`),
    axes: [...new Set(evidence.map((e) => e.field))].slice(0, 3),
    reliability: RELIABILITY[d.confidence_grade] || null,
    reliabilityReason: '',
    conditions,
    conditionStates: conditionStates(c.conditions),
    unrated,
    obstacles,
    // 유형별 건수·재발은 서버가 주지 않아 비워 두고(types), 전체 건수만 보인다. 위치가 정확하지 않은 민원 수는 두 건수의 차이다.
    complaint: {
      has: c.complaint_cnt != null,
      total: c.complaint_cnt ?? 0,
      lowAccuracy: c.complaint_cnt != null && c.complaint_cnt_excl_low != null ? Math.max(0, c.complaint_cnt - c.complaint_cnt_excl_low) : 0,
      types: [],
      recur: 0,
    },
    articles: [],
    dept,
    // 판정이 없으면 서버가 department를 null로 주고 이유(department_reason)를 따로 준다
    deptReason: c.department?.reason || c.department_reason || '',
    deptOptions: [],
    lastYear: null,
    history: [],
    reasonText: record ? record.reason_text || record.reason_code || '' : '',
    memo: record?.memo || '',
    bounds: row?.bounds || null,
    points: null,
    canDecide: !!list?.canDecide,
    showDecisionTab: user?.role === 'district' && !user?.readOnly && list?.run?.status === RUN_STATUS.REVIEW,
    canPickDept: false,
    showRequest: user?.role === 'district' && record?.decision === DECISION.TARGET,
    confirmedByGu: !!list?.myConfirm?.done,
    problems: [],
    request: null,
    org: user?.org || '',
  };
}

/**
 * 우선순위 점수 근거(US-07) 요약. 후보 목록에서 센다. 서버에 없는 값(사용한 자료 수)은 null이다.
 * 3개 구가 모두 확정해 회차 상태가 '확정'일 때만 만들어진다(정의서 US-07).
 */
export function toConditionRecord(list) {
  const run = list.run;
  const rows = [...list.items, ...list.unrated];
  const unrated = Object.values(DOMAIN_LABEL).map((name) => ({ name, count: rows.filter((r) => r.unratedNames.includes(name)).length }));
  return {
    server: true,
    ready: run.status === RUN_STATUS.FINAL,
    run,
    version: run.version,
    candidateCount: rows.length,
    priorityCount: rows.filter((r) => r.conditions.length > 0).length,
    unrated,
    indicators: Object.values(INDICATORS).map((i) => ({ domain: DOMAIN_LABEL[i.domain], label: i.label })),
    dataCount: null,
  };
}

export function createPriorityApi(rawRequest) {
  const request = async (path, options) => snakeKeys(await rawRequest(path, options));
  let lastList = null;
  return {
    /** 회차 목록. 보존 대상 회차는 뺀다. */
    /** finalizedOf(runId) → 3개 구가 모두 확정했는가(서버 값). 상태를 주지 않는 서버에서만 쓴다. */
    async listRuns({ finalizedOf } = {}) {
      const d = await request('/api/priority/runs');
      const runs = (d.runs || []).filter((r) => !PRESERVED_RUN_IDS.has(Number(r.run_id)));
      return Promise.all(
        runs.map(async (r) => {
          const needs = !STATUS_VALUES.has(r.status) && typeof finalizedOf === 'function';
          return toRun(r, { finalized: needs ? await finalizedOf(r.run_id) : false });
        }),
      );
    },
    async listCandidates({ runId, gu, user, guList, allGu, decisions, myConfirm, finalized }) {
      const res = await request(`/api/priority/runs/${encodeURIComponent(runId)}/candidates?limit=3000`);
      lastList = toCandidateList(res, user, { gu, guList, allGu, decisions, myConfirm, finalized });
      return lastList;
    },
    async getCandidateDetail({ runId, gid, user, record }) {
      const c = await request(`/api/priority/runs/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(gid)}`);
      return toCandidateDetail(c, { list: lastList, user, record });
    },
  };
}
