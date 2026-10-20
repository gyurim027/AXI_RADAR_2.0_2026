// 어드민 가짜 서버. RADAR 운영자만 쓴다. 백엔드가 붙으면 이 파일이 하던 일(권한 검사, 규칙 검사)을 서버가 맡는다.
// 화면 코드는 이 파일을 직접 부르지 않고 src/api/admin.js만 부른다.
import { ApiError, realUser } from './server.js';
import { getState, saveState } from './store.js';
import { CLASSIFY_SAMPLES } from './reference.js';
import {
  ACTION_DRAFTS,
  ARTICLE_TEXTS,
  ACCESS_ACTIONS,
  DEPT_DRAFTS,
  INDICATORS,
  LOW_LOCATION,
  OPERATOR_LABEL,
  RELEVANCE,
  ROLE_OPTIONS,
  SCHEDULE,
  SEED_CHECKS,
  SEED_ROLE_LOG,
  STALE_DUE,
  THRESHOLDS,
  UPLOAD_FORMATS,
} from './adminData.js';
import {
  ACTION_IDS,
  actionRows,
  adminState,
  allAccounts,
  allExecutions,
  allRuns,
  allUploads,
  approvalRows,
  accessRows,
  dataItems,
  deptDrafts,
  dotDate,
  dotDateTime,
  fileVersions,
  isCalcDone,
  isoLocal,
  jurisdictionRows,
  logAccess,
  mockNow,
  peopleOf,
  regulations,
  roleLabel,
  runKindLabel,
  versionList,
  versionValues,
} from './adminModel.js';
import { withIga } from '../shared/utils/format.js';
import { GU_LIST, ROLE, RUN_STATUS } from '../shared/constants.js';

const RUN_MS = 3000; // 실행이 '실행 중'으로 보이는 시간 (가짜)

function requireOperator() {
  const u = realUser();
  if (!u) throw new ApiError('unauthorized', '로그인이 필요합니다.');
  if (u.role !== ROLE.OPERATOR) throw new ApiError('forbidden', '볼 수 없습니다.');
  return u;
}
const nowDate = () => dotDate(mockNow());
const stamp = () => {
  saveState();
};

// ------------------------------------------------------------------ 실행: 시간이 지나면 끝난다
function settleExecutions() {
  const a = adminState();
  let changed = false;
  a.executions.forEach((ex) => {
    if (ex.status !== '실행 중' || Date.now() - ex.startedMs < RUN_MS) return;
    const missing = dataItems().some((d) => d.freshness === '빠짐' && d.id === 'DAT-13');
    if (ex.kind === '산정' && missing) {
      ex.status = '실패';
      ex.minutes = 18;
      ex.cause = '보도 면적 열이 비어 있음';
      ex.logs = [...ex.logs, '[실행] 보도 폭 측정 자료를 읽었습니다.', '[실행] 지표 계산 실패: 보도 면적 열이 비어 있음 (격자 3,412개)'];
    } else {
      ex.status = '성공';
      ex.minutes = 20;
      ex.logs = [...ex.logs, '[실행] 끝났습니다. 걸린 시간 20분'];
      if (ex.runId) a.calcDone[ex.runId] = true;
    }
    changed = true;
  });
  if (changed) saveState();
}
function executionsOf(runName) {
  return allExecutions().filter((e) => e.kind === '산정' && e.runName === runName);
}

// ------------------------------------------------------------------ 공통 상단 (AD-00)
export function listAdminRuns() {
  requireOperator();
  settleExecutions();
  return allRuns()
    .map((r) => {
      const ex = executionsOf(r.name);
      return {
        id: r.id,
        name: r.name,
        kind: r.kind,
        kindLabel: runKindLabel(r),
        status: r.status,
        version: r.version,
        created: r.created,
        review: r.review,
        calcDone: isCalcDone(r.id),
        ran: ex.length > 0,
        running: ex.some((e) => e.status === '실행 중'),
        unratedFields: r.unratedFields,
      };
    })
    .sort((x, y) => (x.created < y.created ? 1 : -1));
}

export function listAdminNotifications() {
  const user = requireOperator();
  settleExecutions();
  const s = getState();
  const read = new Set(s.notifRead[user.id] || []);
  const rows = [];
  allExecutions()
    .filter((e) => e.status === '실패')
    .forEach((e) => rows.push({ id: `fail-${e.id}`, kind: 'failure', date: e.at.slice(0, 10).replaceAll('-', '.'), text: `${e.name} 실행이 실패했습니다. 원인을 확인해 주세요.` }));
  dataItems()
    .filter((d) => d.freshness === '갱신 예정일 지남')
    .forEach((d) => rows.push({ id: `stale-${d.id}`, kind: 'staleData', date: STALE_DUE[d.id] || '2026.07.01', text: `${d.name}의 갱신 예정일이 지났습니다. 새 자료를 받아 올려 주세요.` }));
  regulations()
    .filter((r) => !r.seen && !r.pending)
    .forEach((r) => rows.push({ id: `reg-${r.id}`, kind: 'regulation', date: r.date, text: `${withIga(r.name)} 개정되었습니다. 바뀐 조문을 확인해 주세요.` }));
  approvalRows()
    .filter((r) => r.result !== '승인 대기')
    .forEach((r) => {
      const name = r.target === '산정 기준' && r.version !== '-' ? `산정 기준 ${r.version}` : r.target === '담당 부서 표' ? '담당 부서 표 수정안' : r.target;
      rows.push({
        id: `ap-${r.id}`,
        kind: 'approval',
        date: (r.decidedAt || r.at).slice(0, 10).replaceAll('-', '.'),
        text: r.result === '승인' ? `${name} 제안이 승인되었습니다. 다음 산정부터 사용할 수 있습니다.` : `${name} 제안이 돌려보내졌습니다. 사유를 확인해 주세요.`,
      });
    });
  return rows
    .map((n) => ({ ...n, read: read.has(n.id) }))
    .sort((x, y) => (x.date < y.date ? 1 : -1))
    .slice(0, 20);
}
export function markAdminNotificationRead({ id }) {
  const user = requireOperator();
  const s = getState();
  s.notifRead[user.id] = [...new Set([...(s.notifRead[user.id] || []), id])];
  saveState();
  return { ok: true };
}

/** 사용자 화면 보기 (AD-00 4-1): 고르는 창의 선택지 */
export const VIEW_AS_OPTIONS = [
  { value: 'city', label: '성남시 (시 도로과)' },
  { value: 'suj', label: '수정구 (구 도로관리팀)' },
  { value: 'jungwon', label: '중원구 (구 도로관리팀)' },
  { value: 'bundang', label: '분당구 (구 도로관리팀)' },
];
export function listViewAsOptions() {
  requireOperator();
  return VIEW_AS_OPTIONS;
}
export function startViewAs({ accountId }) {
  const user = requireOperator();
  const opt = VIEW_AS_OPTIONS.find((o) => o.value === accountId);
  if (!opt) throw new ApiError('invalid', '고를 수 없는 계정입니다.');
  const s = getState();
  s.viewAs = accountId;
  logAccess(user, '사용자 화면 보기', opt.label);
  saveState();
  return { ok: true, label: opt.label };
}
export function stopViewAs() {
  const s = getState();
  s.viewAs = null;
  saveState();
  return { ok: true };
}
export function viewAsLabel() {
  const s = getState();
  const opt = VIEW_AS_OPTIONS.find((o) => o.value === s.viewAs);
  return opt ? opt.label : null;
}

// ------------------------------------------------------------------ 대시보드 (AD-01)
function nextTask(run) {
  if (run.status === RUN_STATUS.REVIEW) return { key: 'waitConfirm', text: '3개 구의 우선 점검 대상 확정을 기다려 주세요.', to: null };
  if (run.status !== RUN_STATUS.DRAFT) return { key: 'none', text: null, to: null };
  const missing = dataItems().filter((d) => d.freshness === '빠짐').length;
  if (missing > 0) return { key: 'missing', text: `빠진 자료 ${missing}종을 올려 주세요.`, to: '/admin/data/list?freshness=빠짐', toLabel: '데이터 목록' };
  const errors = checkRows().format.length + checkRows().value.length;
  if (errors > 0) return { key: 'checks', text: `검사에서 걸린 자료 ${errors}건을 고쳐 주세요.`, to: '/admin/data/checks', toLabel: '검사 결과' };
  const ex = executionsOf(run.name);
  const ok = isCalcDone(run.id);
  if (!ok && ex.length === 0) return { key: 'calc', text: '산정을 시작해 주세요.', to: '/admin/runs/list', toLabel: '회차 목록' };
  if (!ok && ex.some((e) => e.status === '실행 중')) return { key: 'running', text: '산정이 끝나기를 기다려 주세요.', to: '/admin/runs/log', toLabel: '실행 기록' };
  if (!ok) return { key: 'failed', text: '실행이 실패했습니다. 원인을 확인하고 다시 실행해 주세요.', to: '/admin/runs/log', toLabel: '실행 기록' };
  return { key: 'open', text: '검토 중으로 열어 주세요.', to: '/admin/runs/list', toLabel: '회차 목록' };
}

export function getDashboard({ runId }) {
  requireOperator();
  settleExecutions();
  const run = allRuns().find((r) => r.id === runId);
  if (!run) throw new ApiError('notFound', '회차를 찾을 수 없습니다.');
  const items = dataItems();
  const stale = items.filter((d) => d.freshness === '갱신 예정일 지남').length;
  const missing = items.filter((d) => d.freshness === '빠짐').length;
  const since = mockNow().getTime() - 30 * 24 * 3600 * 1000;
  const recent = allExecutions().filter((e) => new Date(e.at).getTime() >= since);
  const count = (st) => recent.filter((e) => e.status === st).length;
  const approvals = approvalRows();
  return {
    run: { id: run.id, name: run.name, status: run.status },
    next: nextTask(run),
    data: { stale, missing },
    runs: { days: 30, success: count('성공'), failure: count('실패'), warning: count('경고') },
    approvals: {
      pending: approvals.filter((r) => r.result === '승인 대기').length,
      approved: approvals.filter((r) => r.result === '승인').length,
      returned: approvals.filter((r) => r.result === '돌려받음').length,
    },
    regulations: regulations().filter((r) => !r.seen && !r.pending).length,
  };
}

// ------------------------------------------------------------------ 데이터 (AD-02, AD-03, AD-04, AD-05)
export function listData({ freshness = '전체', source = '전체' } = {}) {
  requireOperator();
  const rank = { '빠짐': 0, '갱신 예정일 지남': 1, 최신: 2 };
  return dataItems()
    .filter((d) => (freshness === '전체' || d.freshness === freshness) && (source === '전체' || d.source === source))
    .sort((x, y) => rank[x.freshness] - rank[y.freshness] || (x.id < y.id ? -1 : 1))
    .map((d) => ({ ...d, files: d.uploaded ? fileVersions(d.id) : [] }));
}
export function listUploadTargets() {
  requireOperator();
  // API로 받는 자료는 올리지 않는다 (AD-03 서브 타이틀)
  return dataItems()
    .filter((d) => d.source !== '공공데이터포털 API')
    .map((d) => ({ id: d.id, name: d.name, source: d.source, official: d.official, complaint: d.id === 'DAT-07' }));
}
export function listUploads() {
  requireOperator();
  return allUploads().map((u) => ({ ...u, atLabel: dotDate(u.at) }));
}

export function uploadFile({ dataId, fileName, source, basis, received, official, period }) {
  const user = requireOperator();
  const item = dataItems().find((d) => d.id === dataId);
  if (!item) throw new ApiError('invalid', '자료를 찾을 수 없습니다.');
  const errors = {};
  if (!String(source || '').trim() || !String(basis || '').trim()) errors.sourceBasis = true;
  const ext = String(fileName || '').split('.').pop().toUpperCase();
  if (!fileName || !UPLOAD_FORMATS.includes(ext)) errors.format = true;
  if (errors.sourceBasis || errors.format) return { ok: false, errors };

  const a = adminState();
  const when = mockNow();
  const year = String(basis).slice(0, 4);
  // 가짜 검사 규칙: 파일 이름에 '오류'나 'error'가 들어 있으면 3건이 걸린다. 개발 화면에서 보려는 장치다.
  const bad = /오류|error/i.test(fileName);
  const upload = {
    id: `up-${Date.now()}`,
    at: isoLocal(when),
    by: user.org === 'RADAR 운영팀' ? OPERATOR_LABEL : `${peopleOf(user.id).name} (${user.org})`,
    dataId,
    dataName: item.name,
    basis: `${year}년 기준`,
    source: String(source).trim(),
    file: fileName,
    errors: bad ? 3 : 0,
  };
  a.uploads.unshift(upload);
  a.files[dataId] = [{ run: '지금 작성 중인 회차', at: nowDate().replaceAll('.', '-'), by: upload.by, file: fileName }, ...(a.files[dataId] || [])];
  a.clearedChecks = [...new Set([...a.clearedChecks, dataId])];
  a.generatedChecks = a.generatedChecks || {};
  if (bad) {
    a.generatedChecks[dataId] = [
      { id: `g-${dataId}-1`, dataId, data: item.name, row: 7, kind: '필수 칸 비어 있음', reason: '기준일 칸이 비었음' },
      { id: `g-${dataId}-2`, dataId, data: item.name, row: 12, kind: '필수 칸 비어 있음', reason: '출처 칸이 비었음' },
      { id: `g-${dataId}-3`, dataId, data: item.name, row: 19, kind: '형식이 다름', reason: '숫자 칸에 글자가 들어 있음' },
    ];
  } else {
    delete a.generatedChecks[dataId];
  }
  a.dataOverrides[dataId] = {
    ...(a.dataOverrides[dataId] || {}),
    source: received || item.source,
    official: official || item.official,
    basis: `${year}년 기준`,
    collectedAt: dotDate(when),
    freshness: bad ? item.freshness : '최신',
    note: period ? `민원 접수 기간 ${period}` : undefined,
  };
  logAccess(user, '설정 변경', `${item.name} 파일 올리기`);
  stamp();
  return { ok: true, upload: { ...upload, atLabel: dotDate(upload.at) } };
}

function checkRows() {
  const a = adminState();
  const cleared = new Set(a.clearedChecks);
  const generated = Object.values(a.generatedChecks || {}).flat();
  const keep = (rows) => rows.filter((r) => !cleared.has(r.dataId));
  return {
    format: [...keep(SEED_CHECKS.format), ...generated.filter((g) => g.kind !== '성남시 밖 좌표')],
    value: keep(SEED_CHECKS.value),
    location: SEED_CHECKS.location,
    group: SEED_CHECKS.group,
  };
}
export function getChecks() {
  requireOperator();
  return { ...checkRows(), low: LOW_LOCATION };
}
export function listLowLocation() {
  requireOperator();
  return Array.from({ length: 20 }, (_, i) => ({
    id: `low-${i}`,
    data: '성남데이터넷 연도별 민원 현황',
    row: 20000 + i * 37,
    kind: '위치 낮음',
    reason: '신고 주소의 구와 좌표가 있는 구가 다릅니다.',
  }));
}

export function listClassify({ runId }) {
  requireOperator();
  const run = allRuns().find((r) => r.id === runId);
  const s = getState();
  const items = run && run.hasComplaints ? GU_LIST.flatMap((gu) => CLASSIFY_SAMPLES[gu] || []) : [];
  return {
    run: run ? { id: run.id, name: run.name } : null,
    relevance: RELEVANCE,
    types: [...new Set(Object.values(CLASSIFY_SAMPLES).flat().map((x) => x.label))],
    items: items.map((x, i) => ({
      ...x,
      relevance: s.classify[x.id]?.relevance || (x.label.includes('판단 불가') ? '불명' : '관련'),
      label: s.classify[x.id]?.label || x.label,
      confidence: 68 + ((i * 7) % 28),
      done: s.classify[x.id] ? s.classify[x.id].result : null,
    })),
  };
}
export function markClassifyAdmin({ id, result, relevance, label }) {
  const user = requireOperator();
  const s = getState();
  s.classify[id] = { result, label: label || null, relevance: relevance || null };
  logAccess(user, '설정 변경', `민원 분류 ${result}`);
  saveState();
  return { ok: true };
}

// ------------------------------------------------------------------ 산정 (AD-06, AD-07, AD-08)
export function createRun({ kind, name }) {
  const user = requireOperator();
  const clean = String(name || '').trim();
  if (!clean) return { ok: false, code: 'nameRequired' };
  if (allRuns().some((r) => r.name === clean)) return { ok: false, code: 'duplicate' };
  const a = adminState();
  const s = getState();
  const approved = versionList().filter((v) => v.status === '승인됨').slice(-1)[0];
  const id = `rx${a.extraRuns.length + 1}`;
  a.extraRuns.push({
    id,
    name: clean,
    kind: kind === '반기 참고' ? 'ref' : 'annual',
    status: RUN_STATUS.DRAFT,
    openedAt: null,
    dataRange: '2023.12 ~ 2027.06',
    version: approved ? approved.version : 'v1.2',
    unratedFields: ['연결성'],
    hasComplaints: true,
    conditionCount: 2,
    dataCount: 31,
    created: nowDate(),
    review: null,
  });
  a.calcDone[id] = false;
  s.guConfirm[id] = Object.fromEntries(GU_LIST.map((g) => [g, null]));
  logAccess(user, '설정 변경', `${clean} 회차 만들기`);
  stamp();
  return { ok: true, id };
}
export function getOpenCheck({ runId }) {
  requireOperator();
  const run = allRuns().find((r) => r.id === runId);
  if (!run) throw new ApiError('notFound', '회차를 찾을 수 없습니다.');
  return {
    run: { id: run.id, name: run.name, kind: run.kind },
    missing: dataItems().filter((d) => d.freshness === '빠짐').map((d) => d.name),
    unrated: run.unratedFields.map((f) => (f === '연결성' ? `${f} (공개 자료 없음)` : f)),
  };
}
export function openRun({ runId }) {
  const user = requireOperator();
  settleExecutions();
  const run = allRuns().find((r) => r.id === runId);
  if (!run || run.status !== RUN_STATUS.DRAFT) throw new ApiError('invalid', '열 수 없는 회차입니다.');
  if (!isCalcDone(runId)) return { ok: false, code: 'notFinished' };
  const s = getState();
  const a = adminState();
  const ref = run.kind === 'ref';
  s.runStatus[runId] = ref ? RUN_STATUS.REF : RUN_STATUS.REVIEW;
  s.runReview = { ...(s.runReview || {}), [runId]: nowDate() };
  a.runOpenNotices.unshift(
    { id: `open-${runId}`, runId, runName: run.name, kind: ref ? 'ref' : 'annual', date: nowDate(), roles: [ROLE.CITY, ROLE.DISTRICT] },
  );
  logAccess(user, '설정 변경', `${run.name} 검토 중으로 열기`);
  stamp();
  return { ok: true };
}
export function startCalc({ runId }) {
  const user = requireOperator();
  settleExecutions();
  const run = allRuns().find((r) => r.id === runId);
  if (!run) throw new ApiError('notFound', '회차를 찾을 수 없습니다.');
  const a = adminState();
  a.executions.unshift(newExecution(run, `${run.name} 산정`, '산정'));
  logAccess(user, '설정 변경', `${run.name} 산정 시작`);
  stamp();
  return { ok: true };
}
function newExecution(run, name, kind) {
  return {
    id: `ex-n${Date.now()}`,
    name,
    kind,
    status: '실행 중',
    at: isoLocal(mockNow()),
    minutes: null,
    runName: run ? run.name : '-',
    runId: run ? run.id : null,
    startedMs: Date.now(),
    logs: [`[${isoLocal(mockNow()).slice(11, 16)}] ${kind}을 시작했습니다.`],
  };
}
export function listExecutions({ days = 30, status = '전체' } = {}) {
  requireOperator();
  settleExecutions();
  const since = mockNow().getTime() - Number(days) * 24 * 3600 * 1000;
  return allExecutions()
    .filter((e) => new Date(e.at).getTime() >= since && (status === '전체' || e.status === status))
    .sort((x, y) => (x.at < y.at ? 1 : -1))
    .map((e) => ({ ...e, atLabel: dotDateTime(e.at) }));
}
export function rerunExecution({ id }) {
  const user = requireOperator();
  settleExecutions();
  const ex = allExecutions().find((e) => e.id === id);
  if (!ex || ex.status !== '실패') throw new ApiError('invalid', '다시 실행할 수 없습니다.');
  const run = allRuns().find((r) => r.name === ex.runName);
  const a = adminState();
  a.executions.unshift(newExecution(run, ex.name, ex.kind));
  logAccess(user, '설정 변경', `${ex.name} 처음부터 다시 실행`);
  stamp();
  return { ok: true };
}
export function listSchedule() {
  requireOperator();
  return SCHEDULE;
}

// ------------------------------------------------------------------ 산정 기준 (AD-09, AD-10)
export function listVersions({ status = '전체' } = {}) {
  requireOperator();
  return versionList()
    .filter((v) => status === '전체' || v.status === status)
    .map((v) => ({ ...v, indicatorCount: INDICATORS.length }));
}
export function createVersion() {
  const user = requireOperator();
  const a = adminState();
  const list = versionList();
  const approved = list.filter((v) => v.status === '승인됨').slice(-1)[0];
  const last = list[list.length - 1];
  const next = `v1.${Number(last.version.split('.')[1]) + 1}`;
  a.newVersions.push({ version: next, name: `새 버전 (${approved.version} 복사)`, run: '-', status: '작성 중', updated: nowDate(), base: approved.version });
  a.versionEdits[next] = structuredClone(versionValues(approved.version));
  logAccess(user, '설정 변경', `산정 기준 ${next} 만들기`);
  stamp();
  return { ok: true, version: next };
}
export function getVersion({ version }) {
  requireOperator();
  const meta = versionList().find((v) => v.version === version);
  if (!meta) throw new ApiError('notFound', '버전을 찾을 수 없습니다.');
  const cur = versionValues(version);
  const prev = meta.base ? versionValues(meta.base) : cur;
  return {
    meta: { ...meta, editable: meta.status === '작성 중' || meta.status === '돌려받음' },
    indicators: INDICATORS.map((i) => ({ id: i.id, field: i.field, name: i.name, current: cur.weights[i.id], previous: prev.weights[i.id] })),
    thresholds: THRESHOLDS.map((t) => ({ id: t.id, name: t.name, unit: t.unit, current: cur.thresholds[t.id], previous: prev.thresholds[t.id] })),
    conditions: cur.conditions.map((c) => ({ ...c, previous: (prev.conditions.find((p) => p.id === c.id) || null) })),
  };
}
function changedCount(cur, prev) {
  let delta = 0;
  INDICATORS.forEach((i) => {
    delta += Math.abs((cur.weights[i.id] ?? 0) - (prev.weights[i.id] ?? 0));
  });
  THRESHOLDS.forEach((t) => {
    delta += Math.abs((cur.thresholds[t.id] ?? 0) - (prev.thresholds[t.id] ?? 0)) / 10;
  });
  cur.conditions.forEach((c) => {
    const p = prev.conditions.find((x) => x.id === c.id);
    delta += Math.abs((c.ratio ?? 0) - (p?.ratio ?? 0)) / 2 + (p && p.use !== c.use ? 6 : 0) + (p ? 0 : 6);
  });
  return Math.min(50, Math.round(delta * 0.8));
}
export function saveVersionDraft({ version, values }) {
  requireOperator();
  const meta = versionList().find((v) => v.version === version);
  if (!meta || !(meta.status === '작성 중' || meta.status === '돌려받음')) throw new ApiError('forbidden', '고칠 수 없는 버전입니다.');
  const a = adminState();
  a.versionEdits[version] = structuredClone(values);
  stamp();
  return { ok: true };
}
export function previewChange({ version, values }) {
  requireOperator();
  const meta = versionList().find((v) => v.version === version);
  const prev = meta.base ? versionValues(meta.base) : versionValues(version);
  return { top: 50, changed: changedCount(values, prev), at: isoLocal(mockNow()) };
}
export function requestVersionApproval({ version, values, reason }) {
  const user = requireOperator();
  if (!String(reason || '').trim()) return { ok: false, code: 'reasonRequired' };
  const meta = versionList().find((v) => v.version === version);
  if (!meta || !(meta.status === '작성 중' || meta.status === '돌려받음')) throw new ApiError('forbidden', '요청할 수 없는 버전입니다.');
  const a = adminState();
  const prev = meta.base ? versionValues(meta.base) : versionValues(version);
  a.versionEdits[version] = structuredClone(values);
  const changes = [];
  // 사용자 화면은 분야별 반영 비율로 비교한다 (US-10 1-2). 한 분야 안 지표의 합으로 본다.
  [...new Set(INDICATORS.map((i) => i.field))].forEach((field) => {
    const sum = (w) => INDICATORS.filter((i) => i.field === field).reduce((acc, i) => acc + (w[i.id] ?? 0), 0);
    if (sum(values.weights) !== sum(prev.weights)) changes.push({ type: 'weight', field, from: `${sum(prev.weights)}%`, to: `${sum(values.weights)}%` });
  });
  THRESHOLDS.forEach((t) => {
    if (values.thresholds[t.id] !== prev.thresholds[t.id]) changes.push({ type: 'other', field: t.name, from: `${prev.thresholds[t.id]}${t.unit}`, to: `${values.thresholds[t.id]}${t.unit}` });
  });
  values.conditions.forEach((c) => {
    const p = prev.conditions.find((x) => x.id === c.id);
    if (!p || p.ratio !== c.ratio || p.use !== c.use || p.value !== c.value) changes.push({ type: 'other', field: c.name, from: p ? `${p.ratio}%` : '-', to: `${c.ratio}%${c.use ? '' : ' (사용 안 함)'}` });
  });
  const id = `rq-${Date.now()}`;
  const at = nowDate().replaceAll('.', '-');
  a.requests.push({
    id,
    kind: 'criteria',
    version,
    reason: String(reason).trim(),
    proposal: {
      id,
      kind: '산정 기준',
      version,
      summary: meta.name,
      date: nowDate(),
      changes: changes.length ? changes : [{ type: 'other', field: '변경 없음', from: '-', to: '-' }],
      impact: { top: 50, changed: changedCount(values, prev) },
      proposerLabel: OPERATOR_LABEL,
      at,
      ref: { kind: 'criteria', version },
    },
  });
  logAccess(user, '설정 변경', `산정 기준 ${version} 승인 요청`, String(reason).trim());
  stamp();
  return { ok: true };
}

// ------------------------------------------------------------------ 담당 부서 표 (AD-11)
export function getDept() {
  requireOperator();
  return {
    current: jurisdictionRows(),
    drafts: deptDrafts().map((d) => ({ ...d })),
  };
}
export function getArticle({ draftId }) {
  requireOperator();
  const d = DEPT_DRAFTS.find((x) => x.id === draftId);
  if (!d) throw new ApiError('notFound', '찾을 수 없습니다.');
  return { title: d.basis, text: d.article, extra: ARTICLE_TEXTS[d.jurId] || null };
}
export function requestDeptApproval({ draftId, reason }) {
  const user = requireOperator();
  const d = DEPT_DRAFTS.find((x) => x.id === draftId);
  if (!d) throw new ApiError('notFound', '찾을 수 없습니다.');
  if (!String(reason || '').trim()) return { ok: false, code: 'reasonRequired' };
  const a = adminState();
  const id = `rq-${Date.now()}`;
  a.requests.push({
    id,
    kind: 'dept',
    draftId,
    jurId: d.jurId,
    to: d.to,
    basis: d.basis,
    reason: String(reason).trim(),
    proposal: {
      id,
      kind: '담당 부서 표',
      version: null,
      summary: `${d.problem}: ${d.from} → ${d.to}`,
      date: nowDate(),
      changes: [{ type: 'other', field: d.problem, from: d.from, to: d.to }],
      impact: null,
      proposerLabel: OPERATOR_LABEL,
      at: nowDate().replaceAll('.', '-'),
      ref: { kind: 'dept', draftId },
    },
  });
  logAccess(user, '설정 변경', `담당 부서 표 수정안 승인 요청`, String(reason).trim());
  stamp();
  return { ok: true };
}

// ------------------------------------------------------------------ 규정 변경 (AD-12)
export function listRegulationChanges() {
  requireOperator();
  return regulations().sort((x, y) => (x.date < y.date ? 1 : -1));
}
export function markRegulationSeen({ id }) {
  requireOperator();
  const a = adminState();
  if (!a.regSeen.includes(id)) a.regSeen.push(id);
  stamp();
  return { ok: true };
}

// ------------------------------------------------------------------ 조치 제안 표 (AD-13)
export function getActionTable() {
  requireOperator();
  const a = adminState();
  return {
    rows: actionRows(),
    drafts: ACTION_DRAFTS.filter((d) => !a.actionDraftsDone.includes(d.id)).map((d) => ({
      ...d,
      ck: ACTION_IDS[d.actionId],
      problem: actionRows().find((r) => r.id === d.actionId).problem,
    })),
  };
}
export function saveActionRow({ id, patch }) {
  const user = requireOperator();
  const row = actionRows().find((r) => r.id === id);
  if (!row) throw new ApiError('notFound', '행을 찾을 수 없습니다.');
  if (patch.sentence !== undefined && !String(patch.sentence).trim()) return { ok: false, code: 'sentenceRequired' };
  const a = adminState();
  a.actionEdits[id] = { ...(a.actionEdits[id] || {}), ...patch };
  logAccess(user, '설정 변경', `조치 제안 표 ${row.ck} 저장`);
  stamp();
  return { ok: true, ck: row.ck };
}
export function getDraftArticle({ draftId }) {
  requireOperator();
  const d = ACTION_DRAFTS.find((x) => x.id === draftId);
  if (!d) throw new ApiError('notFound', '찾을 수 없습니다.');
  return { title: d.article, text: d.articleText };
}
export function saveActionDraft({ draftId }) {
  const user = requireOperator();
  const d = ACTION_DRAFTS.find((x) => x.id === draftId);
  if (!d) throw new ApiError('notFound', '찾을 수 없습니다.');
  const a = adminState();
  a.actionEdits[d.actionId] = { ...(a.actionEdits[d.actionId] || {}), sentence: d.sentence, article: d.article, review: '검토 완료' };
  a.actionDraftsDone.push(draftId);
  logAccess(user, '설정 변경', `조치 제안 문장 틀 ${ACTION_IDS[d.actionId]} 저장`);
  stamp();
  return { ok: true, ck: ACTION_IDS[d.actionId] };
}
export function recordAdminDownload({ name }) {
  const user = requireOperator();
  logAccess(user, '파일 내려받기', name);
  stamp();
  return { ok: true };
}

// ------------------------------------------------------------------ 승인 이력 (AD-14)
export function listApprovals({ days = 365 } = {}) {
  requireOperator();
  const since = mockNow().getTime() - Number(days) * 24 * 3600 * 1000;
  return approvalRows().filter((r) => new Date(r.at).getTime() >= since);
}

// ------------------------------------------------------------------ 계정 (AD-15)
export function listAccounts() {
  requireOperator();
  const a = adminState();
  return {
    rows: allAccounts().map((acc) => {
      const p = peopleOf(acc.id);
      return {
        id: acc.id,
        name: p.name,
        role: roleLabel(acc.role),
        gu: acc.gu || '-',
        team: p.team,
        status: acc.stopped ? '멈춤' : '사용 중',
        last: p.last,
      };
    }),
    log: [...a.roleLog, ...SEED_ROLE_LOG].sort((x, y) => (x.at < y.at ? 1 : -1)),
    roles: ROLE_OPTIONS,
  };
}
export function createAccount({ role, gu, team, name, loginId }) {
  const user = requireOperator();
  if (role === '구 도로관리팀' && !gu) return { ok: false, code: 'guRequired' };
  if (!String(name || '').trim() || !String(loginId || '').trim()) return { ok: false, code: 'required' };
  if (allAccounts().some((x) => x.id === String(loginId).trim())) return { ok: false, code: 'duplicate' };
  const a = adminState();
  const mapped = role === '시 도로과' ? ROLE.CITY : role === 'RADAR 운영자' ? ROLE.OPERATOR : ROLE.DISTRICT;
  const teamName = String(team || '').trim() || (mapped === ROLE.DISTRICT ? '도로관리팀' : mapped === ROLE.CITY ? '도로관리팀' : 'RADAR 운영팀');
  const org = mapped === ROLE.DISTRICT ? `${gu} 건설과 ${teamName}` : mapped === ROLE.CITY ? `성남시 도로과 ${teamName}` : teamName;
  a.newAccounts.push({ id: String(loginId).trim(), role: mapped, gu: mapped === ROLE.DISTRICT ? gu : null, org, name: String(name).trim(), team: teamName });
  a.roleLog.unshift({ id: `rl-${Date.now()}`, at: nowDate().replaceAll('.', '-'), name: String(name).trim(), from: '-', to: role, by: OPERATOR_LABEL });
  logAccess(user, '설정 변경', `계정 만들기 ${String(loginId).trim()}`);
  stamp();
  return { ok: true };
}
export function setAccountStatus({ id, status }) {
  const user = requireOperator();
  const acc = allAccounts().find((x) => x.id === id);
  if (!acc) throw new ApiError('notFound', '계정을 찾을 수 없습니다.');
  if (acc.id === user.id) throw new ApiError('forbidden', '내 계정은 멈출 수 없습니다.');
  const a = adminState();
  const p = peopleOf(id);
  if (status === '멈춤') a.accountStatus[id] = '멈춤';
  else delete a.accountStatus[id];
  a.roleLog.unshift({
    id: `rl-${Date.now()}`,
    at: nowDate().replaceAll('.', '-'),
    name: p.name,
    from: status === '멈춤' ? roleLabel(acc.role) : '-',
    to: status === '멈춤' ? '-' : roleLabel(acc.role),
    by: OPERATOR_LABEL,
  });
  logAccess(user, '설정 변경', `계정 ${status === '멈춤' ? '사용 멈추기' : '다시 쓰기'} ${id}`);
  stamp();
  return { ok: true };
}

// ------------------------------------------------------------------ 접속 기록, 알림 설정 (AD-16, AD-17)
export function listAccess({ days = 30, accountId = '전체', action = '전체' } = {}) {
  requireOperator();
  const since = mockNow().getTime() - Number(days) * 24 * 3600 * 1000;
  const people = (id) => (id ? peopleOf(id).name : null);
  return {
    actions: ACCESS_ACTIONS,
    accounts: allAccounts().map((x) => ({ value: x.id, label: `${peopleOf(x.id).name} (${x.org})` })),
    rows: accessRows()
      .filter((r) => new Date(r.at).getTime() >= since)
      .filter((r) => (accountId === '전체' || r.accountId === accountId) && (action === '전체' || r.action === action))
      .map((r) => ({
        ...r,
        atLabel: dotDateTime(r.at),
        who: r.accountId ? `${people(r.accountId)} (${r.actor})` : r.actor,
      })),
  };
}
export function getAlertEmail() {
  requireOperator();
  return { value: adminState().alertEmails };
}
export function saveAlertEmail({ value }) {
  const user = requireOperator();
  const list = String(value || '')
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean);
  const ok = list.length > 0 && list.every((x) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(x));
  if (!ok) return { ok: false, code: 'format' };
  adminState().alertEmails = list.join(', ');
  logAccess(user, '설정 변경', '실패 알림 받을 메일');
  stamp();
  return { ok: true };
}
