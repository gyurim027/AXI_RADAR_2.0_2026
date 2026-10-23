import test from 'node:test';
import assert from 'node:assert/strict';
import { BackendError, createBackendClient } from '../src/api/backend.js';
import { approvalErrorMessage, createApprovalApi, proposalRow } from '../src/api/approvals.js';

const response = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

test('JWT와 검토 본문만 전송하고 승인자 ID를 만들지 않는다', async () => {
  let seen;
  const request = createBackendClient({ baseUrl: 'http://localhost:8000/', getToken: () => 'verified-token',
    fetchImpl: async (...args) => { seen = args; return response({ ok: true }); } });
  const api = createApprovalApi(request);
  await api.decide({ id: 17, approve: false, reason: '  근거 보완  ' });
  assert.equal(seen[0], 'http://localhost:8000/api/approvals/17/review');
  assert.equal(seen[1].headers.Authorization, 'Bearer verified-token');
  assert.deepEqual(JSON.parse(seen[1].body), { decision: '돌려보냄', reviewComment: '근거 보완' });
});

test('서버 오류의 status·code·message와 승인/반영 상태를 보존한다', async () => {
  const details = { status: 409, code: 'table_changed', message: '표가 바뀌었습니다', approvalStatus: '승인', departmentApplied: false };
  const request = createBackendClient({ fetchImpl: async () => response({ error: details }, 409) });
  await assert.rejects(request('/api/approvals/1/review'), (e) => e.status === 409 && e.code === 'table_changed' && e.message === details.message && e.details.approvalStatus === '승인');
});

test('연결 실패는 성공이나 목업 결과로 바꾸지 않는다', async () => {
  let calls = 0;
  const request = createBackendClient({ fetchImpl: async () => { calls++; throw new TypeError('offline'); } });
  await assert.rejects(request('/api/approvals'), (e) => e.code === 'network_error');
  assert.equal(calls, 1);
});

test('JSON이 아닌 401도 세션 만료로 처리한다', async () => {
  let cleared = false;
  const request = createBackendClient({ fetchImpl: async () => new Response('expired', { status: 401 }), onUnauthorized: () => { cleared = true; } });
  await assert.rejects(request('/api/auth/me'), (e) => e.code === 'invalid_response');
  assert.equal(cleared, true);
});

test('정상 401 오류 계약과 재로그인 처리를 함께 보존한다', async () => {
  let cleared = 0;
  const request = createBackendClient({ fetchImpl: async () => response({ error: { code: 'login_required', message: '로그인 필요' } }, 401), onUnauthorized: () => cleared++ });
  await assert.rejects(request('/api/approvals'), (e) => e.code === 'login_required');
  assert.equal(cleared, 1);
});

test('반영 결과를 확인할 수 없는 응답은 성공으로 표시하지 않는다', async () => {
  const request = createBackendClient({ fetchImpl: async () => new Response('bad gateway', { status: 502 }) });
  await assert.rejects(request('/api/approvals/1/apply', { method: 'POST' }), (e) => e.code === 'invalid_response');
});

test('제안과 미반영 목록을 합쳐도 반영을 자동 호출하지 않는다', async () => {
  const calls = [];
  const api = createApprovalApi(async (path) => {
    calls.push(path);
    return path.includes('unapplied') ? { proposals: [{ settingVersionId: 2, contentRef: '저장된 수정안', approvedAt: '2026-10-23T11:00:00' }] }
      : { proposals: [{ settingVersionId: 1, settingKind: '기준값', contentRef: '저장된 기준', approvalStatus: '제안' }] };
  });
  const rows = await api.list();
  assert.equal(rows.length, 2);
  assert.equal(rows[1].pendingApply, true);
  assert.equal(rows[1].status, '승인');
  assert.equal(rows[1].kind, '담당 부서 표');
  assert.equal(calls.length, 2);
  assert.ok(calls.every((p) => !p.endsWith('/apply')));
});

test('비부서표 설정의 원문을 점수·기여점·영향 수치로 해석하지 않는다', async () => {
  const row = proposalRow({ settingVersionId: 1, settingKind: '기준값', contentRef: '{"기준":"검토대상"}' });
  const api = createApprovalApi(async () => { throw new Error('호출하면 안 됨'); });
  const result = await api.preview(row);
  assert.equal(result.content, row.content);
  assert.deepEqual(result.changes, []);
  assert.equal(result.impact, undefined);
});

test('부서표 비교는 실제 preview 응답을 사용한다', async () => {
  const api = createApprovalApi(async (path) => { assert.equal(path, '/api/approvals/3/preview'); return { problem: '보도 파손', before: '수정구: 건설과', after: '중원구: 보도팀' }; });
  const r = await api.preview({ id: 3, kind: '담당 부서 표' });
  assert.deepEqual(r.changes, [{ field: '보도 파손', from: '수정구: 건설과', to: '중원구: 보도팀' }]);
});

test('승인 뒤 반영 실패 안내가 승인 기록을 숨기지 않는다', () => {
  const e = new BackendError(422, 'needs_review', '확인이 필요합니다', { approvalStatus: '승인', departmentApplied: false });
  assert.match(approvalErrorMessage(e), /승인은 기록됐습니다/);
  assert.match(approvalErrorMessage(e), /반영되지 않았습니다/);
});

test('반영 여부 불명확 상태를 미반영 확정으로 바꾸지 않는다', () => {
  const e = new BackendError(503, 'department_apply_failed', '다시 확인하세요', { approvalStatus: '승인', departmentApplied: null });
  assert.match(approvalErrorMessage(e), /반영 여부를 확인/);
  assert.doesNotMatch(approvalErrorMessage(e), /반영되지 않았습니다/);
});

test('재시도는 지정한 제안 하나만 호출하고 승인 API를 재호출하지 않는다', async () => {
  const seen = [];
  const api = createApprovalApi(async (...args) => { seen.push(args); return { ok: true, departmentApplied: true }; });
  await api.apply({ id: 17 });
  assert.deepEqual(seen, [['/api/approvals/17/apply', { method: 'POST' }]]);
});
