// 어드민이 바꾼 값이 사용자 화면에도 이어지는 곳을 모았다 (회차, 계정, 데이터 목록, 제안, 조치 제안 표).
// server.js(사용자 화면)와 adminServer.js(어드민)가 같이 쓰므로 둘 중 어느 쪽도 가져오지 않는다.
import { ACCOUNTS } from './accounts.js';
import { RUNS } from './runs.js';
import { ACTION_TABLE, PROPOSALS } from './reference.js';
import {
  ADMIN_REGULATIONS,
  DATA_ITEMS,
  DEPT_DRAFTS,
  INDICATORS,
  JURISDICTION,
  MOCK_NOW,
  OPERATOR_LABEL,
  SEED_ACCESS,
  SEED_APPROVALS,
  SEED_EXECUTIONS,
  SEED_FILES,
  SEED_PEOPLE,
  SEED_UPLOADS,
  SEED_VERSIONS,
  THRESHOLDS,
  VERSION_VALUES,
} from './adminData.js';
import { getState } from './store.js';
import { GU_LIST, ROLE, RUN_STATUS } from '../shared/constants.js';

const LOAD_MS = Date.now();
/** 가짜 서버의 "지금". 고정한 날(2026.11.20)에서 시작해 화면을 연 뒤 지난 시간만큼 흐른다. */
export function mockNow() {
  return new Date(new Date(MOCK_NOW).getTime() + (Date.now() - LOAD_MS));
}
const pad = (n) => String(n).padStart(2, '0');
export const dotDate = (d) => {
  const x = d instanceof Date ? d : new Date(d);
  return `${x.getFullYear()}.${pad(x.getMonth() + 1)}.${pad(x.getDate())}`;
};
export const dotDateTime = (d) => {
  const x = d instanceof Date ? d : new Date(d);
  return `${dotDate(x)} ${pad(x.getHours())}:${pad(x.getMinutes())}`;
};
export const isoLocal = (d) => {
  const x = d instanceof Date ? d : new Date(d);
  return `${x.getFullYear()}-${pad(x.getMonth() + 1)}-${pad(x.getDate())}T${pad(x.getHours())}:${pad(x.getMinutes())}:00`;
};

export function adminState() {
  const s = getState();
  if (!s.admin) {
    s.admin = {
      extraRuns: [], // 새로 만든 회차
      periodEdits: {}, // { 회차: { start, end } | null } 산정 시작 전에 고친 민원 접수 기간
      calcDone: {}, // { 회차: true } 산정이 끝난 회차
      executions: [], // 어드민에서 새로 돌린 실행
      uploads: [], // 새로 올린 기록
      dataOverrides: {}, // { 데이터 ID: 바뀐 칸 }
      files: {}, // { 데이터 ID: 새로 올린 원본 목록 }
      clearedChecks: [], // 다시 올려서 사라진 검사 결과 (데이터 ID)
      generatedChecks: {}, // { 데이터 ID: 새로 올린 파일에서 걸린 행 }
      newVersions: [], // 새로 만든 산정 기준 버전
      versionEdits: {}, // { 버전: { weights, thresholds, conditions } } 고친 값 (전체)
      requests: [], // 승인 요청 (산정 기준, 담당 부서 표)
      regSeen: [], // 확인한 규정 변경
      actionEdits: {}, // { 항목 ID: 바뀐 칸 }
      actionDraftsDone: [], // 저장한 문장 틀 초안
      newAccounts: [], // 새로 만든 계정
      accountStatus: {}, // { 아이디: '멈춤' }
      roleLog: [], // 권한 변경 기록
      alertEmails: 'radar-ops@example.com',
      runOpenNotices: [], // 회차를 열 때 사용자에게 가는 알림
      adminNoticeRead: [],
    };
  }
  return s.admin;
}

// ------------------------------------------------------------------ 회차
/** 회차별 부가 정보 (만든 날, 검토 시작일). 정렬은 만든 날 최신 순이다. */
const RUN_META = {
  r2028: { created: '2026.11.15', review: null },
  r2027: { created: '2026.10.01', review: '2026.11.01' },
  r2026h2: { created: '2026.07.01', review: '2026.07.15' },
  r2026: { created: '2025.11.01', review: '2025.12.01' },
};
export function allRuns() {
  const s = getState();
  const a = adminState();
  const edits = a.periodEdits || {};
  return [...RUNS, ...a.extraRuns].map((r) => ({
    ...r,
    // 산정 시작 전에 고친 민원 접수 기간이 있으면 그것을 쓴다. 기간이 없으면 민원 없이 산정하는 회차다.
    complaintPeriod: r.id in edits ? edits[r.id] : r.complaintPeriod || null,
    hasComplaints: r.id in edits ? !!edits[r.id] : r.hasComplaints,
    status: s.runStatus[r.id] || r.status,
    created: RUN_META[r.id]?.created || r.created,
    review: s.runReview?.[r.id] || RUN_META[r.id]?.review || r.review || null,
  }));
}
export function runKindLabel(run) {
  return run.kind === 'ref' ? '반기 참고' : '연간';
}
export function isCalcDone(runId) {
  const a = adminState();
  if (a.calcDone[runId] !== undefined) return a.calcDone[runId];
  return runId !== 'r2028' && !a.extraRuns.some((r) => r.id === runId);
}

// ------------------------------------------------------------------ 데이터
export function dataItems() {
  const a = adminState();
  return DATA_ITEMS.map((d) => ({ ...d, ...(a.dataOverrides[d.id] || {}) }));
}
export function fileVersions(dataId) {
  const a = adminState();
  return [...(a.files[dataId] || []), ...(SEED_FILES[dataId] || [])];
}
/** 사용자 화면 데이터 목록(US-12)이 쓰는 모양 */
export function dataListForUser() {
  return dataItems().map((d) => ({
    id: d.userKey,
    name: d.name,
    org: d.org,
    basis: d.basis || '기준일 미확인',
    updateType: d.cycle,
    freshness: d.freshness,
    share: d.share,
  }));
}
export function allUploads() {
  const a = adminState();
  return [...a.uploads, ...SEED_UPLOADS].sort((x, y) => (x.at < y.at ? 1 : -1));
}

// ------------------------------------------------------------------ 실행
export function allExecutions() {
  const a = adminState();
  return [...a.executions, ...SEED_EXECUTIONS];
}

// ------------------------------------------------------------------ 산정 기준
export function versionList() {
  const a = adminState();
  const s = getState();
  const base = [...SEED_VERSIONS, ...a.newVersions];
  return base.map((v) => {
    const req = a.requests.filter((r) => r.kind === 'criteria' && r.version === v.version).slice(-1)[0];
    let status = v.status;
    let returnedReason = null;
    const reqId = req ? req.id : v.version === 'v1.3' ? 'p1' : null;
    if (reqId) {
      const decided = s.proposals[reqId];
      if (decided) {
        status = decided.result === '승인' ? '승인됨' : '돌려받음';
        returnedReason = decided.result === '반려' ? decided.reason : null;
      } else if (req || v.version === 'v1.3') {
        status = '승인 대기';
      }
    }
    return { ...v, status, returnedReason, requestId: reqId };
  });
}
export function versionValues(version) {
  const a = adminState();
  if (a.versionEdits[version]) return a.versionEdits[version];
  const meta = versionList().find((v) => v.version === version);
  const given = VERSION_VALUES[version];
  const baseValues = meta?.base ? versionValues(meta.base) : null;
  const weights = Object.fromEntries(INDICATORS.map((i) => [i.id, i.weight]));
  if (!given) return baseValues || { weights, thresholds: defaultThresholds(), conditions: [] };
  if (!baseValues) {
    return {
      weights: { ...weights, ...given.weights },
      thresholds: { ...defaultThresholds(), ...given.thresholds },
      conditions: given.conditions,
    };
  }
  return {
    weights: { ...baseValues.weights, ...given.weights },
    thresholds: { ...baseValues.thresholds, ...given.thresholds },
    conditions: given.conditions || baseValues.conditions,
  };
}
function defaultThresholds() {
  return Object.fromEntries(THRESHOLDS.map((t) => [t.id, t.value]));
}

// ------------------------------------------------------------------ 담당 부서 표, 규정
export function jurisdictionRows() {
  const a = adminState();
  const s = getState();
  // 시 도로과가 승인한 수정안은 현재 표에 반영된다 (AD-11 1-2)
  const approved = a.requests.filter((r) => r.kind === 'dept' && s.proposals[r.id]?.result === '승인');
  return JURISDICTION.map((j) => {
    const hit = approved.filter((r) => r.jurId === j.id).slice(-1)[0];
    return hit ? { ...j, dept: hit.to, basis: hit.basis } : j;
  });
}
export function deptDrafts() {
  const a = adminState();
  const s = getState();
  return DEPT_DRAFTS.filter((d) => {
    const req = a.requests.filter((r) => r.kind === 'dept' && r.draftId === d.id).slice(-1)[0];
    if (!req) return true;
    return s.proposals[req.id]?.result === '반려'; // 돌려받으면 다시 보인다
  });
}
export function regulations() {
  const a = adminState();
  return ADMIN_REGULATIONS.map((r) => ({ ...r, seen: a.regSeen.includes(r.id) }));
}

// ------------------------------------------------------------------ 제안 · 승인 (사용자 화면 승인 대기 = 시 도로과)
export function allProposals() {
  const a = adminState();
  return [
    ...PROPOSALS.map((p) => ({ ...p, proposerLabel: OPERATOR_LABEL, at: '2026-11-03' })),
    ...a.requests.map((r) => r.proposal),
  ];
}
export function pendingProposals() {
  const s = getState();
  return allProposals().filter((p) => !s.proposals[p.id]);
}

export function approvalRows() {
  const s = getState();
  const rows = allProposals().map((p) => {
    const decided = s.proposals[p.id];
    return {
      id: p.id,
      target: p.kind,
      version: p.version || '-',
      proposer: p.proposerLabel || OPERATOR_LABEL,
      at: p.at || '2026-11-03',
      approver: decided ? decided.by || '박사례 (성남시 도로과 도로관리팀)' : '-',
      result: decided ? (decided.result === '승인' ? '승인' : '돌려받음') : '승인 대기',
      reason: decided?.reason || '-',
      decidedAt: decided?.at || null,
      ref: p.ref,
    };
  });
  return [...rows, ...SEED_APPROVALS].sort((x, y) => (x.at < y.at ? 1 : -1));
}

// ------------------------------------------------------------------ 조치 제안 표
export const ACTION_IDS = Object.fromEntries(ACTION_TABLE.map((r, i) => [r.id, `CK-${(i + 1) * 10}`]));
export function actionRows() {
  const a = adminState();
  return ACTION_TABLE.map((r) => ({
    ...r,
    ck: ACTION_IDS[r.id],
    review: '검토 완료',
    ...(a.actionEdits[r.id] || {}),
  }));
}

// ------------------------------------------------------------------ 계정
export function allAccounts() {
  const a = adminState();
  return [...ACCOUNTS, ...a.newAccounts].map((acc) => ({ ...acc, stopped: a.accountStatus[acc.id] === '멈춤' }));
}
export function peopleOf(id) {
  const a = adminState();
  const extra = a.newAccounts.find((x) => x.id === id);
  if (extra) return { name: extra.name, team: extra.team, last: '-' };
  return SEED_PEOPLE[id] || { name: id, team: '-', last: '-' };
}
export function roleLabel(role) {
  return role === ROLE.CITY ? '시 도로과' : role === ROLE.DISTRICT ? '구 도로관리팀' : 'RADAR 운영자';
}

// ------------------------------------------------------------------ 접속 기록
const IP = { operator: '10.12.3.45', city: '10.12.1.9', suj: '10.12.8.21', jungwon: '10.12.8.30', bundang: '10.12.9.12', 'bundang-sidewalk': '10.12.9.14' };
/** 접속 기록 한 줄을 남긴다. 고치거나 지우는 함수는 만들지 않는다 (I-04) */
export function logAccess(user, action, target = '-', reason = '-') {
  if (!user) return;
  const s = getState();
  s.accessLog.push({
    at: isoLocal(mockNow()),
    actor: user.org,
    accountId: user.id,
    ip: IP[user.id] || '10.12.0.1',
    action,
    target,
    reason,
    row: true,
  });
}
export function accessRows() {
  const s = getState();
  const live = s.accessLog
    .filter((x) => x.row)
    .map((x) => ({ ...x }));
  // 예전 형식(내려받기만 남긴 줄)도 보인다
  const legacy = s.accessLog
    .filter((x) => !x.row)
    .map((x) => ({
      at: x.at.slice(0, 19),
      actor: x.actor,
      accountId: null,
      ip: '10.12.0.1',
      action: '파일 내려받기',
      target: x.reportName || '-',
      reason: '-',
    }));
  return [...live, ...legacy, ...SEED_ACCESS].sort((x, y) => (x.at < y.at ? 1 : -1)).map((r, i) => ({ ...r, key: String(i) }));
}

export const GU = GU_LIST;
export { RUN_STATUS };
