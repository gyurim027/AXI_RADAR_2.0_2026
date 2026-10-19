// 가짜 서버. 백엔드가 붙으면 이 파일이 하던 일(역할별 걸러 내리기, 규칙 검사)을 서버가 맡는다.
// 화면 코드는 이 파일을 직접 부르지 않고 src/api/*.js만 부른다.
import { ACCOUNTS, MOCK_PASSWORD } from './accounts.js';
import { RUNS } from './runs.js';
import {
  DATASET,
  OB,
  OBSTACLES,
  PRIORITY_CONDITIONS,
  DECISION_REASONS,
  DEPT_OPTIONS,
  contactOf,
  deptNameFor,
} from './generate.js';
import {
  NOTIFICATIONS,
  DATA_LIST,
  REGULATIONS,
  PROPOSALS,
  CLASSIFY_SAMPLES,
  ACTION_TABLE,
} from './reference.js';
import { getState, saveState } from './store.js';
import { ALL_GU, DECISION, DEPT_STATUS, GU_LIST, ROLE, RUN_STATUS } from '../shared/constants.js';
import { formatDate, runNameWithoutRef } from '../shared/utils/format.js';

const MAX_FAILS = 5; // CM-01 2: 5번 틀리면 10분 동안 잠근다
const LOCK_MINUTES = 10;

export class ApiError extends Error {
  constructor(code, message) {
    super(message || code);
    this.code = code;
  }
}

const today = () => formatDate(new Date());
const todayIso = () => new Date().toISOString().slice(0, 10);
const baseOf = (gid) => DATASET.bases.find((b) => b.gid === gid);

// ------------------------------------------------------------------ 계정
export function currentUser() {
  const s = getState();
  return ACCOUNTS.find((a) => a.id === s.session) || null;
}
function requireUser() {
  const u = currentUser();
  if (!u) throw new ApiError('unauthorized', '로그인이 필요합니다.');
  return u;
}

export function login(loginId, password) {
  const s = getState();
  const rec = s.loginFails[loginId] || { count: 0, lockedUntil: 0 };
  const now = Date.now();
  if (rec.lockedUntil > now) {
    return { ok: false, reason: 'locked', lockMinutes: LOCK_MINUTES };
  }
  const account = ACCOUNTS.find((a) => a.id === loginId);
  if (!account || password !== MOCK_PASSWORD) {
    const count = rec.count + 1;
    if (count >= MAX_FAILS) {
      s.loginFails[loginId] = { count: 0, lockedUntil: now + LOCK_MINUTES * 60 * 1000 };
      saveState();
      return { ok: false, reason: 'locked', lockMinutes: LOCK_MINUTES };
    }
    s.loginFails[loginId] = { count, lockedUntil: 0 };
    saveState();
    return { ok: false, reason: 'wrong', remaining: MAX_FAILS - count, lockMinutes: LOCK_MINUTES };
  }
  s.loginFails[loginId] = { count: 0, lockedUntil: 0 };
  s.session = account.id;
  saveState();
  return { ok: true, user: publicUser(account) };
}

export function logout() {
  const s = getState();
  s.session = null;
  saveState();
}

export function publicUser(a) {
  return { id: a.id, role: a.role, gu: a.gu, org: a.org };
}

// ------------------------------------------------------------------ 회차
function liveStatus(run) {
  const s = getState();
  return s.runStatus[run.id] || run.status;
}
function allConfirmed(runId) {
  const c = getState().guConfirm[runId];
  return GU_LIST.every((g) => c && c[g]);
}

/** 사용자 화면에서 볼 수 있는 회차: 산정 중은 보이지 않는다 (US-00 1-1) */
export function listRuns() {
  requireUser();
  return RUNS.map((r) => ({ ...r, status: liveStatus(r) }))
    .filter((r) => r.status !== RUN_STATUS.DRAFT)
    .map(({ openedAt, ...r }) => ({ ...r, openedAt }));
}
function getRun(runId) {
  const r = RUNS.find((x) => x.id === runId);
  if (!r) throw new ApiError('notFound', '회차를 찾을 수 없습니다.');
  const status = liveStatus(r);
  if (status === RUN_STATUS.DRAFT) throw new ApiError('notFound', '회차를 찾을 수 없습니다.');
  return { ...r, status };
}

// ------------------------------------------------------------------ 후보
function scopeGus(user, gu) {
  if (user.role === ROLE.DISTRICT) return [user.gu];
  if (gu && gu !== ALL_GU) return [gu];
  return GU_LIST;
}

function obstaclesOf(run, base, complaint) {
  return base.obstacles.filter((k) => {
    if (!k.startsWith('park')) return true;
    return run.hasComplaints && complaint.total > 0;
  });
}

function deptResolved(runId, base, obstacleKey) {
  const s = getState();
  const chosen = s.deptChoice[runId]?.[base.gid];
  if (chosen) return { name: chosen, contact: contactOf(chosen), status: DEPT_STATUS.OK };
  if (obstacleKey) {
    // 요청안의 항목별 받는 부서는 관할 매핑을 따른다
    const name = deptNameFor(OB[obstacleKey].deptKind, base.gu);
    if (!name) return null;
    return { name, contact: contactOf(name), status: DEPT_STATUS.OK };
  }
  if (!base.dept) return null;
  return { name: base.dept, contact: contactOf(base.dept), status: base.deptStatus };
}

/** 회차의 후보를 합쳐 만든다 (결정·부서 선택 반영) */
function mergedItems(run) {
  const s = getState();
  const list = DATASET.byRun[run.id] || [];
  return list.map((it) => {
    const base = baseOf(it.gid);
    const ov = s.decisions[run.id]?.[it.gid];
    const decision = ov ? ov.decision : it.decision;
    return {
      it,
      base,
      decision,
      reasonText: ov ? ov.reasonText : it.reasonText,
      memo: ov ? ov.memo : it.memo,
      history: ov ? [...it.history, ...ov.history] : it.history,
      obstacles: obstaclesOf(run, base, it.complaint),
    };
  });
}

function percentLabel(rank, total) {
  return Math.max(1, Math.ceil((rank / total) * 100));
}

function toRow(m, rank, scopeTotal, cityRank, cityTotal) {
  const { it, base } = m;
  const rated = it.score != null;
  const tierRatio = rated ? rank / scopeTotal : 1;
  const tier = !rated ? 'unrated' : tierRatio <= 0.1 ? 'top' : tierRatio <= 0.3 ? 'mid' : 'rest';
  const obstacleNames = m.obstacles.map((k) => OB[k].name);
  const notSurveyed = it.score == null ? base.unrated.filter((u) => u.reason === '조사 안 함') : base.unrated.filter((u) => u.reason === '조사 안 함');
  return {
    gid: base.gid,
    rank: rated ? rank : null,
    gu: base.gu,
    address: base.address,
    landmark: base.landmark,
    score: it.score,
    tier,
    obstacleMain: obstacleNames[0] || '-',
    obstacleRest: Math.max(0, obstacleNames.length - 1),
    obstacleNames,
    reliability: base.reliability,
    unratedCount: base.unrated.length,
    unratedAll: base.unratedAll,
    notSurveyed: notSurveyed.map((u) => u.name),
    collected: base.collected,
    missing: base.missing,
    decision: m.decision,
    conditions: it.conditions,
    inProtectionZone: base.inProtectionZone,
    complaintFlag: base.complaintFlag,
    recur: it.complaint.recur > 0,
    bounds: base.bounds,
    points: base.points,
    cityPercent: rated ? percentLabel(cityRank, cityTotal) : null,
  };
}

/** 후보 목록(US-01). 도로관리팀에는 자기 구 값만 내려보낸다. */
export function listCandidates({ runId, gu }) {
  const user = requireUser();
  const run = getRun(runId);
  const all = mergedItems(run);
  const cityRated = all.filter((m) => m.it.score != null).sort((a, b) => b.it.score - a.it.score);
  const cityRankOf = new Map(cityRated.map((m, i) => [m.it.gid, i + 1]));

  const allowed = scopeGus(user, null); // 이 계정이 볼 수 있는 구 전체
  const scoped = all.filter((m) => allowed.includes(m.base.gu));
  const scopedRated = scoped.filter((m) => m.it.score != null).sort((a, b) => b.it.score - a.it.score);
  const rankOf = new Map(scopedRated.map((m, i) => [m.it.gid, i + 1]));

  const rows = scopedRated.map((m) =>
    toRow(m, rankOf.get(m.it.gid), scopedRated.length, cityRankOf.get(m.it.gid), cityRated.length),
  );
  const unrated = scoped
    .filter((m) => m.it.score == null)
    .map((m) => toRow(m, 0, scopedRated.length, 0, cityRated.length));

  // 걸러 보기: 시 도로과의 구 선택. 숫자(결정 현황)는 허용된 구 전체 기준이다.
  const wantGus = scopeGus(user, gu);
  const visible = rows.filter((r) => wantGus.includes(r.gu));
  const visibleUnrated = unrated.filter((r) => wantGus.includes(r.gu));

  const counts = { total: rows.length, none: 0, target: 0, exclude: 0, hold: 0 };
  rows.forEach((r) => {
    if (r.decision === DECISION.NONE) counts.none++;
    else if (r.decision === DECISION.TARGET) counts.target++;
    else if (r.decision === DECISION.EXCLUDE) counts.exclude++;
    else counts.hold++;
  });

  return {
    run,
    guScope: user.role === ROLE.DISTRICT ? user.gu : gu || ALL_GU,
    items: visible,
    unrated: visibleUnrated,
    counts,
    // 조건이 정해지기 전에는 우선 확인 조건 묶음을 숨긴다 (US-01 1-3)
    conditions: run.conditionCount > 0 ? PRIORITY_CONDITIONS.slice(0, run.conditionCount) : [],
    guBoundaries: DATASET.boundaries,
    // 문제 유형 선택지는 보행 방해요소 DB에서 가져온다 (US-01 2-1)
    obstacleOptions: OBSTACLES.map((o) => o.name).filter((n, i, arr) => arr.indexOf(n) === i),
    myConfirm: user.role === ROLE.DISTRICT ? confirmOf(runId, user.gu) : null,
    // 결정 상태 칸을 버튼으로 보일지: 도로관리팀 · 검토 중 회차 · 자기 구를 아직 확정하기 전 (CM-00 10번)
    canDecide: user.role === ROLE.DISTRICT && run.status === RUN_STATUS.REVIEW && !confirmOf(runId, user.gu).done,
  };
}

function confirmOf(runId, gu) {
  const d = getState().guConfirm[runId]?.[gu] || null;
  return { gu, done: !!d, date: d ? formatDate(d) : null };
}

/** 후보 상세(US-03) */
export function getCandidateDetail({ runId, gid }) {
  const user = requireUser();
  const run = getRun(runId);
  const all = mergedItems(run);
  const m = all.find((x) => x.it.gid === gid);
  if (!m) throw new ApiError('notFound', '후보를 찾을 수 없습니다.');
  if (user.role === ROLE.DISTRICT && m.base.gu !== user.gu) {
    throw new ApiError('forbidden', '볼 수 없는 후보입니다.');
  }
  const { it, base } = m;
  const cityRated = all.filter((x) => x.it.score != null).sort((a, b) => b.it.score - a.it.score);
  const cityRank = cityRated.findIndex((x) => x.it.gid === gid) + 1;
  const allowed = scopeGus(user, null);
  const scopedRated = cityRated.filter((x) => allowed.includes(x.base.gu));
  const rank = scopedRated.findIndex((x) => x.it.gid === gid) + 1;

  const dept = deptResolved(runId, base, null);
  const ownGu = user.role === ROLE.DISTRICT && base.gu === user.gu;
  const reviewing = run.status === RUN_STATUS.REVIEW;
  const confirmed = ownGu ? confirmOf(runId, user.gu).done : false;
  const canDecide = ownGu && reviewing && !confirmed;

  // 요청안·조치 제안 (⑥)
  const problems = [];
  const seen = new Set();
  m.obstacles.forEach((k) => {
    const o = OB[k];
    if (seen.has(o.problem)) return;
    seen.add(o.problem);
    const d = deptResolved(runId, base, k);
    let sentence = o.sentence;
    if (o.deptKind === 'parking') {
      sentence = `이번 회차 자료에 인도·횡단보도 불법 주정차 민원이 ${it.complaint.total}건 있고, ${it.complaint.recur}건은 다시 들어왔습니다. 지금도 주정차가 반복되는지 확인하고 단속을 요청해 주세요.`;
    }
    problems.push({
      key: k,
      problem: o.problem,
      sentence,
      dept: d ? d.name : null,
      article: o.article,
    });
  });
  const first = m.obstacles[0] ? OB[m.obstacles[0]] : null;
  const top3 = it.evidence.slice(0, 3).map((e) => e.short);
  const request = first
    ? {
        content: first.requestContent,
        basis: top3,
      }
    : null;

  const axes = [...new Set(it.evidence.map((e) => e.field))].slice(0, 3);

  return {
    run,
    gid,
    rank,
    cityRank,
    cityPercent: it.score != null ? percentLabel(cityRank, cityRated.length) : null,
    gu: base.gu,
    address: base.address,
    landmark: base.landmark,
    score: it.score,
    decision: m.decision,
    explanation: it.explanation,
    evidence: it.evidence,
    topEvidence: top3,
    axes,
    reliability: base.reliability,
    reliabilityReason: base.reliabilityReason,
    unrated: base.unrated,
    obstacles: m.obstacles.map((k) => OB[k].name),
    complaint: {
      has: run.hasComplaints,
      ...it.complaint,
    },
    articles: it.articles,
    dept: dept ? { ...dept } : null,
    deptReason: `${OB[m.obstacles[0]]?.name || '-'} / ${base.road} / ${base.inProtectionZone ? '보호구역 안' : '보호구역 밖'}`,
    deptOptions: DEPT_OPTIONS,
    lastYear: it.lastYear || null,
    history: [...m.history].reverse(), // 최신 순
    reasonText: m.reasonText,
    memo: m.memo,
    bounds: base.bounds,
    points: base.points,
    canDecide,
    showDecisionTab: ownGu && reviewing, // ⑤ 탭: 검토 중 회차의 자기 구 후보에서만 보인다
    canPickDept: ownGu && reviewing && !confirmed,
    showRequest: ownGu && m.decision === DECISION.TARGET,
    confirmedByGu: confirmed,
    problems,
    request,
    org: user.org,
  };
}

/** 결정 저장(G-03). 사유 규칙은 US-03 5-2를 따른다. */
export function saveDecision({ runId, gid, decision, reasonKey, reasonText, memo }) {
  const user = requireUser();
  const run = getRun(runId);
  const base = baseOf(gid);
  if (user.role !== ROLE.DISTRICT || base.gu !== user.gu) throw new ApiError('forbidden', '결정할 수 없습니다.');
  if (run.status !== RUN_STATUS.REVIEW) throw new ApiError('forbidden', '결정할 수 없는 회차입니다.');
  if (confirmOf(runId, user.gu).done) throw new ApiError('locked', '이미 확정한 구입니다.');
  if (![DECISION.TARGET, DECISION.EXCLUDE, DECISION.HOLD].includes(decision)) {
    throw new ApiError('invalid', '결정 값이 맞지 않습니다.');
  }
  const needReason = decision !== DECISION.TARGET;
  if (needReason && !reasonKey) return { ok: false, code: 'reasonRequired' };
  if (reasonKey === '기타' && !String(reasonText || '').trim()) return { ok: false, code: 'otherRequired' };
  if (reasonKey && !DECISION_REASONS.includes(reasonKey)) throw new ApiError('invalid', '사유 값이 맞지 않습니다.');

  const s = getState();
  const m = mergedItems(run).find((x) => x.it.gid === gid);
  const from = m.decision;
  const finalReason = reasonKey === '기타' ? String(reasonText).trim().slice(0, 100) : reasonKey || null;
  const finalMemo = reasonKey === '기타' ? null : memo ? String(memo).slice(0, 200) : null;
  s.decisions[runId] = s.decisions[runId] || {};
  const prev = s.decisions[runId][gid];
  s.decisions[runId][gid] = {
    decision,
    reasonKey: reasonKey || null,
    reasonText: finalReason,
    memo: finalMemo,
    // 결정은 회차, 산정 기준 버전과 함께 저장한다 (US-03 5-1)
    runId,
    criteriaVersion: run.version,
    history: [...(prev ? prev.history : []), ...(from !== decision ? [{ date: today(), from, to: decision, org: user.org }] : [])],
  };
  s.changeLog.push({ at: new Date().toISOString(), actor: user.org, kind: '결정', gid, from, to: decision });
  saveState();
  return { ok: true };
}

/** 담당 부서 정하기(F-04 → G-04 변경 기록) */
export function setDept({ runId, gid, deptName }) {
  const user = requireUser();
  const run = getRun(runId);
  const base = baseOf(gid);
  if (user.role !== ROLE.DISTRICT || base.gu !== user.gu) throw new ApiError('forbidden', '정할 수 없습니다.');
  if (run.status !== RUN_STATUS.REVIEW || confirmOf(runId, user.gu).done) {
    throw new ApiError('forbidden', '정할 수 없는 회차입니다.');
  }
  if (!DEPT_OPTIONS.includes(deptName)) throw new ApiError('invalid', '부서 값이 맞지 않습니다.');
  const s = getState();
  s.deptChoice[runId] = s.deptChoice[runId] || {};
  s.deptChoice[runId][gid] = deptName;
  s.changeLog.push({ at: new Date().toISOString(), actor: user.org, kind: '담당 부서', gid, to: deptName });
  saveState();
  return { ok: true };
}


/** 구별 비교(US-01 3-1, D-07). 시 도로과만 본다 (ISS-029). 점수 구조(ISS-013) 결정 후 변동 예정. */
export function getGuCompare({ runId }) {
  const user = requireUser();
  if (user.role !== ROLE.CITY) throw new ApiError('forbidden', '볼 수 없습니다.');
  const run = getRun(runId);
  const rated = mergedItems(run)
    .filter((m) => m.it.score != null)
    .sort((a, b) => b.it.score - a.it.score);
  const top = rated.slice(0, Math.ceil(rated.length * 0.3)); // 상위 구간 크기는 가정 (ISS-013)
  // 보행자 사고 비율과 보정 전 비율은 가짜 값이다 (D-07: 사고를 뺀 점수와 구별 사고 분포 비교)
  const accident = { 수정구: 34, 중원구: 28, 분당구: 38 };
  const before = { 수정구: 45, 중원구: 22, 분당구: 33 };
  return {
    run,
    rows: GU_LIST.map((gu) => ({
      gu,
      topRatio: Math.round((top.filter((m) => m.base.gu === gu).length / top.length) * 100),
      accidentRatio: accident[gu],
      beforeRatio: before[gu],
    })),
  };
}

// ------------------------------------------------------------------ 구 확정 (G-06)
export function getConfirmSummary({ runId }) {
  const user = requireUser();
  const run = getRun(runId);
  const all = mergedItems(run);
  if (user.role === ROLE.DISTRICT) {
    const mine = all.filter((m) => m.base.gu === user.gu && m.it.score != null);
    const c = { target: 0, exclude: 0, hold: 0, none: 0 };
    mine.forEach((m) => {
      if (m.decision === DECISION.TARGET) c.target++;
      else if (m.decision === DECISION.EXCLUDE) c.exclude++;
      else if (m.decision === DECISION.HOLD) c.hold++;
      else c.none++;
    });
    // 구 사용자에게는 자기 구만 내려보낸다 (ISS-029)
    return { role: ROLE.DISTRICT, gu: user.gu, counts: c, mine: confirmOf(runId, user.gu) };
  }
  if (user.role === ROLE.CITY) {
    return { role: ROLE.CITY, guStatuses: GU_LIST.map((g) => confirmOf(runId, g)) };
  }
  throw new ApiError('forbidden', '볼 수 없습니다.');
}

export function confirmGu({ runId }) {
  const user = requireUser();
  const run = getRun(runId);
  if (user.role !== ROLE.DISTRICT) throw new ApiError('forbidden', '확정할 수 없습니다.');
  if (run.status !== RUN_STATUS.REVIEW) throw new ApiError('forbidden', '확정할 수 없는 회차입니다.');
  const s = getState();
  s.guConfirm[runId] = s.guConfirm[runId] || {};
  if (s.guConfirm[runId][user.gu]) throw new ApiError('locked', '이미 확정했습니다.');
  s.guConfirm[runId][user.gu] = todayIso();
  s.changeLog.push({ at: new Date().toISOString(), actor: user.org, kind: '구 확정', to: user.gu });
  // 3개 구가 모두 확정하면 회차가 확정된다. 이 사실은 구 사용자에게 따로 알리지 않는다.
  if (allConfirmed(runId)) s.runStatus[runId] = RUN_STATUS.FINAL;
  saveState();
  return confirmOf(runId, user.gu);
}

// ------------------------------------------------------------------ 보고서 (4-4)
function reportScope(user, runId) {
  const run = getRun(runId);
  const all = mergedItems(run);
  const gus = user.role === ROLE.DISTRICT ? [user.gu] : GU_LIST;
  return { run, items: all.filter((m) => gus.includes(m.base.gu) && m.it.score != null), gus };
}

/** US-05 관할 부서별 연간 보고서 (도로관리팀만) */
export function getAnnualReport({ runId }) {
  const user = requireUser();
  if (user.role !== ROLE.DISTRICT) throw new ApiError('forbidden', '볼 수 없습니다.');
  const { run, items } = reportScope(user, runId);
  const ready = confirmOf(runId, user.gu).done; // 구 확정을 한 뒤에 만들 수 있다 (H-01)
  const groups = new Map();
  if (ready) {
    items
      .filter((m) => m.decision === DECISION.TARGET)
      .forEach((m) => {
        const d = deptResolved(runId, m.base, null);
        const key = d ? d.name : '담당 미정';
        groups.set(key, (groups.get(key) || 0) + 1);
      });
  }
  return {
    run,
    ready,
    rows: [...groups.entries()].map(([dept, count]) => ({ dept, count })).sort((a, b) => b.count - a.count),
  };
}

function mainBasis(items) {
  const counter = new Map();
  items.forEach((m) => {
    if (m.it.evidence.some((e) => e.field === '사고')) counter.set('사고 다발지', (counter.get('사고 다발지') || 0) + 1);
    m.obstacles.forEach((k) => counter.set(OB[k].name, (counter.get(OB[k].name) || 0) + 1));
  });
  return [...counter.entries()].sort((a, b) => b[1] - a[1]).slice(0, 2).map(([n]) => n).join(', ') || '-';
}

/** US-06 구별 우선 점검 근거표 */
export function getBasisTable({ runId }) {
  const user = requireUser();
  const { run, items, gus } = reportScope(user, runId);
  const rows = gus.map((gu) => {
    const mine = items.filter((m) => m.base.gu === gu);
    const targets = mine.filter((m) => m.decision === DECISION.TARGET);
    return {
      gu,
      candidates: mine.length,
      targets: targets.length,
      basis: mainBasis(targets.length ? targets : mine.slice(0, 20)),
    };
  });
  return { run, rows, draftReady: run.status === RUN_STATUS.FINAL };
}

/** US-07 산정 조건 기록서 */
export function getConditionRecord({ runId }) {
  requireUser();
  const run = getRun(runId);
  return {
    run,
    ready: run.status === RUN_STATUS.FINAL,
    dataCount: run.dataCount,
    version: run.version,
    unratedFields: run.unratedFields,
    conditionCount: run.conditionCount,
  };
}

/** US-08 보호구역 안팎 비교표 (시 도로과) */
export function getProtectionCompare({ runId }) {
  const user = requireUser();
  if (user.role !== ROLE.CITY) throw new ApiError('forbidden', '볼 수 없습니다.');
  const { run, items } = reportScope(user, runId);
  const sorted = [...items].sort((a, b) => b.it.score - a.it.score);
  const top = sorted.slice(0, Math.ceil(sorted.length * 0.3)); // 상위 구간 (가정, ISS-013)
  return {
    run,
    inside: top.filter((m) => m.base.inProtectionZone).length,
    outside: top.filter((m) => !m.base.inProtectionZone).length,
  };
}

/** US-09 반기 변경 요약 */
export function getHalfYearSummary({ runId }) {
  const user = requireUser();
  const run = getRun(runId);
  const gus = user.role === ROLE.DISTRICT ? [user.gu] : GU_LIST;
  const a = DATASET.byRun.r2026;
  const b = DATASET.byRun.r2026h2;
  const rankMap = (list) => {
    const rated = list.filter((x) => x.score != null && gus.includes(baseOf(x.gid).gu)).sort((p, q) => q.score - p.score);
    return new Map(rated.map((x, i) => [x.gid, i + 1]));
  };
  const ra = rankMap(a);
  const rb = rankMap(b);
  const changes = [...rb.entries()]
    .map(([gid, nr]) => ({ gid, from: ra.get(gid), to: nr }))
    .filter((c) => c.from && Math.abs(c.from - c.to) >= 12)
    .sort((p, q) => Math.abs(q.from - q.to) - Math.abs(p.from - p.to))
    .slice(0, 5)
    .map((c) => ({ gid: c.gid, address: baseOf(c.gid).address, from: c.from, to: c.to }));
  const targets = b
    .filter((x) => x.decision === DECISION.TARGET && gus.includes(baseOf(x.gid).gu))
    .slice(0, 3)
    .map((x, i) => ({
      gid: x.gid,
      address: baseOf(x.gid).address,
      changed: ['민원 재발 1건 늘어남', '보행자 사고 다발지 기준일 갱신', '주정차 단속 2건 늘어남'][i],
    }));
  return {
    run,
    changedData: [
      { name: '주정차 단속 기록', from: '2026.06', to: '2026.12' },
      { name: '성남데이터넷 연도별 민원 현황', from: '2026.06', to: '2026.12' },
    ],
    rankChanges: changes,
    changedTargets: targets,
  };
}

/** 내려받기. 실제 파일은 백엔드가 만든다. 가안은 보고서 미리 보기 내용을 표로 만든다. */
export function recordDownload({ runId, reportName, format }) {
  const user = requireUser();
  const s = getState();
  s.accessLog.push({
    at: new Date().toISOString(),
    actor: user.org,
    action: '내려받기',
    runId,
    reportName,
    format,
  });
  saveState();
  return { ok: true };
}

// ------------------------------------------------------------------ 알림 (US-00 4-1)
export function listNotifications() {
  const user = requireUser();
  const s = getState();
  const read = new Set(s.notifRead[user.id] || []);
  const review = RUNS.find((r) => r.status === RUN_STATUS.REVIEW);
  const ref = RUNS.find((r) => r.status === RUN_STATUS.REF);
  const ctx = {
    version: PROPOSALS[0].version,
    runName: review.name,
    refName: runNameWithoutRef(ref.name),
    gu: user.gu,
  };
  return NOTIFICATIONS.filter((n) => n.roles.includes(user.role))
    .map((n) => ({
      id: n.id,
      kind: n.kind,
      text: n.text(ctx),
      date: n.date,
      read: read.has(n.id),
      targetRunId: n.kind === 'halfYear' ? ref.id : n.kind === 'runOpen' ? review.id : null,
    }))
    .sort((a, b) => (a.date < b.date ? 1 : -1))
    .slice(0, 20);
}
export function markNotificationRead({ id }) {
  const user = requireUser();
  const s = getState();
  s.notifRead[user.id] = [...new Set([...(s.notifRead[user.id] || []), id])];
  saveState();
  return { ok: true };
}

// ------------------------------------------------------------------ 기준정보 (3)
export function listProposals() {
  const user = requireUser();
  if (user.role !== ROLE.CITY) throw new ApiError('forbidden', '볼 수 없습니다.');
  const s = getState();
  return PROPOSALS.filter((p) => !s.proposals[p.id]);
}
export function decideProposal({ id, approve, reason }) {
  const user = requireUser();
  if (user.role !== ROLE.CITY) throw new ApiError('forbidden', '할 수 없습니다.');
  if (!approve && !String(reason || '').trim()) return { ok: false, code: 'reasonRequired' };
  const s = getState();
  s.proposals[id] = { result: approve ? '승인' : '반려', reason: approve ? null : String(reason).trim() };
  s.changeLog.push({ at: new Date().toISOString(), actor: user.org, kind: approve ? '제안 승인' : '제안 반려', gid: id });
  saveState();
  return { ok: true };
}

export function listClassifySamples({ runId }) {
  const user = requireUser();
  if (user.role !== ROLE.DISTRICT) throw new ApiError('forbidden', '볼 수 없습니다.');
  const run = getRun(runId);
  const s = getState();
  return {
    run,
    available: run.hasComplaints,
    labels: OBSTACLES.map((o) => o.name).filter((n, i, arr) => arr.indexOf(n) === i),
    items: run.hasComplaints
      ? (CLASSIFY_SAMPLES[user.gu] || []).map((x) => ({ ...x, done: s.classify[x.id] || null }))
      : [],
  };
}
export function markClassify({ id, result, label }) {
  const user = requireUser();
  if (user.role !== ROLE.DISTRICT) throw new ApiError('forbidden', '할 수 없습니다.');
  const s = getState();
  s.classify[id] = { result, label: label || null };
  saveState();
  return { ok: true };
}

export function listDataList() {
  requireUser();
  return DATA_LIST;
}
export function listRegulations() {
  requireUser();
  return REGULATIONS;
}
export function listActionTable() {
  requireUser();
  return ACTION_TABLE;
}
