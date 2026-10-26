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
