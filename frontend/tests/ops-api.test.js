import test from 'node:test';
import assert from 'node:assert/strict';
import { createBackendClient } from '../src/api/backend.js';
import { createOpsApi } from '../src/api/ops.js';

const response = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const apiWith = (fetchImpl, opts = {}) => createOpsApi(createBackendClient({ baseUrl: 'http://localhost:8000', getToken: () => 'op-token', fetchImpl, ...opts }));

test('계정 만들기 성공은 임시 비밀번호를 그대로 돌려준다', async () => {
  let seen;
  const api = apiWith(async (...a) => { seen = a; return response({ ok: true, id: 'new1', tempPassword: 'q3Zr0x_8LmPa', notice: '한 번만 보입니다.' }); });
  const r = await api.createAccount({ role: '구 도로관리팀', gu: '분당구', team: '', name: '최보도', loginId: 'new1' });
  assert.deepEqual(r, { ok: true, id: 'new1', tempPassword: 'q3Zr0x_8LmPa', notice: '한 번만 보입니다.' });
  assert.equal(seen[0], 'http://localhost:8000/api/admin/accounts');
  assert.equal(seen[1].headers.Authorization, 'Bearer op-token');
  assert.deepEqual(JSON.parse(seen[1].body), { role: '구 도로관리팀', gu: '분당구', team: null, name: '최보도', loginId: 'new1' });
});

test('계정 만들기 입력 오류는 목업과 같은 { ok:false, code }로 바꾼다', async () => {
  for (const [status, code, want] of [[400, 'gu_required', 'guRequired'], [400, 'required', 'required'], [409, 'duplicate', 'duplicate']]) {
    const api = apiWith(async () => response({ error: { status, code, message: 'x' } }, status));
    assert.deepEqual(await api.createAccount({ role: '시 도로과', name: 'a', loginId: 'b' }), { ok: false, code: want });
  }
});

test('모르는 오류(권한 없음 등)는 바꾸지 않고 그대로 던진다', async () => {
  const api = apiWith(async () => response({ error: { status: 403, code: 'forbidden_role', message: 'x' } }, 403));
  await assert.rejects(api.createAccount({ role: '시 도로과', name: 'a', loginId: 'b' }), (e) => e.code === 'forbidden_role');
});

test('접속 기록은 전체를 빼고 조건만 보내고, 줄마다 key를 붙인다', async () => {
  let url;
  const api = apiWith(async (u) => { url = u; return response({ actions: ['로그인'], accounts: [], rows: [{ id: 41, action: '로그인' }] }); });
  const d = await api.listAccess({ days: '30', accountId: '전체', action: '로그인' });
  assert.equal(url, 'http://localhost:8000/api/admin/access?days=30&action=%EB%A1%9C%EA%B7%B8%EC%9D%B8');
  assert.equal(d.rows[0].key, 41);
});

test('알림 메일 형식 오류는 { ok:false, code:"format" }로 바꾼다', async () => {
  const api = apiWith(async () => response({ error: { status: 422, code: 'format', message: 'x' } }, 422));
  assert.deepEqual(await api.saveAlertEmail({ value: 'bad' }), { ok: false, code: 'format' });
});

test('401 오류 코드를 로그인 화면 쪽에 넘긴다 (멈춘 계정·바뀐 역할)', async () => {
  const seen = [];
  const request = createBackendClient({ fetchImpl: async () => response({ error: { status: 401, code: 'account_inactive', message: 'x' } }, 401), onUnauthorized: (c) => seen.push(c) });
  await assert.rejects(request('/api/admin/accounts'), (e) => e.status === 401);
  assert.deepEqual(seen, ['account_inactive']);
});

test('계정 상태 바꾸기: 내 계정·없는 계정 오류는 { ok:false, code }로 바꾼다', async () => {
  for (const [status, code, want] of [[403, 'self_change', 'selfChange'], [404, 'account_not_found', 'notFound']]) {
    const api = apiWith(async () => response({ error: { status, code, message: 'x' } }, status));
    assert.deepEqual(await api.setAccountStatus({ id: 'op', status: '멈춤' }), { ok: false, code: want });
  }
  const ok = apiWith(async () => response({ ok: true, changed: true }));
  assert.deepEqual(await ok.setAccountStatus({ id: 'suj', status: '멈춤' }), { ok: true });
});

test('알림 메일 저장 표가 없으면 { ok:false, code:"tableMissing" }', async () => {
  const api = apiWith(async () => response({ error: { status: 503, code: 'setting_table_missing', message: 'x' } }, 503));
  assert.deepEqual(await api.saveAlertEmail({ value: 'a@b.kr' }), { ok: false, code: 'tableMissing' });
});

test('대시보드: 서버가 모르는 칸(null)은 그대로 두고, 없는 묶음만 채운다', async () => {
  const api = apiWith(async () => response({
    run: { id: 3, name: null, status: null },
    next: { key: 'checks', text: '검사에서 걸린 자료 1301건을 고쳐 주세요.', to: '/admin/data/checks', toLabel: '검사 결과' },
    data: { stale: null, missing: null, unscheduled: null, total: null },
    checks: { fix: 1301, reference: 3147, unreviewed: 4448 },
    criteria: { id: 12, kind: '가중치', label: '가중치 v3', pending: true, status: '승인 대기', at: '2026.10.20', to: '/admin/standards/criteria/12' },
    runs: { days: 30, success: 1, failure: 1, warning: 0, running: 0, skipped: 0 },
    approvals: null, regulations: null,
  }));
  const d = await api.getDashboard();
  assert.equal(d.run.name, null);
  assert.equal(d.data.stale, null);
  assert.deepEqual(d.checks, { fix: 1301, reference: 3147 });
  assert.equal(d.criteria.id, 12);
  assert.equal(d.approvals, null);
  assert.equal(d.next.toLabel, '검사 결과');
});

test('실행 기록: 상태를 서버 이름으로 보내고, 줄 목록과 한 건(로그 포함)을 따로 받는다', async () => {
  const urls = [];
  const api = apiWith(async (u) => {
    urls.push(u);
    return u.includes('/runs/7') ? response({ id: 7, logs: ['[14:11] 시작'], canRerun: true }) : response({ runs: [{ id: 7, name: 'A-11', status: '실패', canRerun: true }] });
  });
  const rows = await api.listExecutions({ days: '30', status: '실패' });
  assert.equal(rows[0].id, 7);
  assert.equal(urls[0], 'http://localhost:8000/api/ops/runs?days=30&status=%EC%8B%A4%ED%8C%A8');
  await api.listExecutions({ days: '7', status: '전체' });
  assert.equal(urls[1], 'http://localhost:8000/api/ops/runs?days=7');
  assert.deepEqual((await api.getExecution({ id: 7 })).logs, ['[14:11] 시작']);
});

test('다시 실행 오류 4가지는 { ok:false, code }로 바꾸고, 그 밖의 오류는 던진다', async () => {
  for (const [code, want] of [['not_failed', 'notFailed'], ['rerun_not_supported', 'notSupported'], ['rerun_input_missing', 'notSupported'], ['already_running', 'alreadyRunning']]) {
    const api = apiWith(async () => response({ error: { status: 409, code, message: 'x' } }, 409));
    assert.deepEqual(await api.rerunExecution({ id: 7 }), { ok: false, code: want });
  }
  const gone = apiWith(async () => response({ error: { status: 404, code: 'run_not_found', message: 'x' } }, 404));
  await assert.rejects(gone.rerunExecution({ id: 7 }), (e) => e.code === 'run_not_found');
  let seen;
  const ok = apiWith(async (...a) => { seen = a; return response({ ok: true, rerunOf: 7 }, 202); });
  assert.deepEqual(await ok.rerunExecution({ id: 7 }), { ok: true });
  assert.equal(seen[1].method, 'POST');
});
