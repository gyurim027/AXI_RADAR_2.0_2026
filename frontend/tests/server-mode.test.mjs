import test from 'node:test';
import assert from 'node:assert/strict';

// 서버 모드는 import.meta.env 값으로 정해지므로, 환경을 바꿔 모듈을 새로 불러와 확인한다.
async function load(env) {
  const { createServer } = await import('vite');
  const server = await createServer({ configFile: false, envFile: false, logLevel: 'silent', server: { middlewareMode: true }, appType: 'custom', define: Object.fromEntries(Object.entries(env).map(([k, v]) => [`import.meta.env.${k}`, JSON.stringify(v)])) });
  try {
    return { backend: await server.ssrLoadModule('/src/api/backend.js'), client: await server.ssrLoadModule('/src/api/client.js'), close: () => server.close() };
  } catch (e) { await server.close(); throw e; }
}

test('서버 주소만 적어도 서버 모드이고 연결된 기능이 모두 켜진다', async () => {
  const m = await load({ VITE_API_BASE_URL: 'http://127.0.0.1:8000' });
  try {
    assert.equal(m.backend.backendAuthEnabled, true);
    assert.equal(m.backend.i07BackendEnabled && m.backend.settingsBackendEnabled && m.backend.opsBackendEnabled, true);
  } finally { await m.close(); }
});

test("서버 주소가 있어도 스위치를 'false'로 적으면 그 기능만 꺼진다", async () => {
  const m = await load({ VITE_API_BASE_URL: 'http://x', VITE_I07_API: 'false' });
  try {
    assert.equal(m.backend.i07BackendEnabled, false);
    assert.equal(m.backend.settingsBackendEnabled, true);
  } finally { await m.close(); }
});

test('주소도 스위치도 없으면 연습용(가짜 서버) 모드다', async () => {
  const m = await load({});
  try {
    assert.equal(m.backend.backendAuthEnabled, false);
  } finally { await m.close(); }
});

test('서버 모드에서는 가짜 서버를 부르지 않고 not_connected를 던진다', async () => {
  const m = await load({ VITE_API_BASE_URL: 'http://127.0.0.1:8000' });
  try {
    let called = false;
    const fn = m.client.mockCall('x', () => { called = true; return 'fake'; });
    await assert.rejects(fn(), (e) => e.code === 'not_connected');
    assert.equal(called, false);
  } finally { await m.close(); }
});

test('연습용 모드에서는 가짜 서버를 그대로 부른다', async () => {
  const m = await load({});
  try {
    const fn = m.client.mockCall('x', () => 'fake');
    assert.equal(await fn(), 'fake');
  } finally { await m.close(); }
});

test('서버 모드에서 어드민 회차 목록은 /admin/runs/list로 열리고 /admin/runs는 열리지 않는다', async () => {
  const { createServer } = await import('vite');
  const server = await createServer({ configFile: false, envFile: false, logLevel: 'silent', server: { middlewareMode: true }, appType: 'custom', define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('http://127.0.0.1:8000') } });
  try {
    const routes = await server.ssrLoadModule('/src/admin/serverRoutes.js');
    assert.equal(routes.isOpenInServerMode('/admin/runs/list'), true);
    assert.equal(routes.isOpenInServerMode('/admin/runs/list/'), true);
    assert.equal(routes.isOpenInServerMode('/admin/runs'), false);
    assert.equal(routes.isOpenInServerMode('/admin/runs/log'), true);
  } finally { await server.close(); }
});

test('서버 연결 모드의 메뉴는 열리는 화면만 남기고, 하위 메뉴가 모두 빠진 묶음은 뺀다', async () => {
  const { buildMenu } = await import('../src/shared/auth/permissions.js');
  const open = (to) => ['/candidates', '/reports/conditions'].includes(to);
  const menu = buildMenu({ role: 'district' }, open);
  assert.deepEqual(menu.map((m) => m.key), ['candidates', 'reports']);
  assert.deepEqual(menu[1].items.map((i) => i.to), ['/reports/conditions']);
  // 연습용 모드(거르지 않음)는 모든 메뉴를 그대로 보인다
  assert.ok(buildMenu({ role: 'district' }).some((m) => m.key === 'reference'));
});

test('민원 분류 검수: 서버 표본을 화면 모양으로 바꾸고, 모르는 칸은 null로 둔다', async () => {
  const { toClassifyItem, createClassifyApi } = await import('../src/api/classify.js');
  assert.deepEqual(toClassifyItem({ id: 7, gu: '수정구', summary: '보도 파손', relevance: '관련', label: '보도 파손', keywords: '파손', confidence: 82, done: null }), {
    id: 7, gu: '수정구', summary: '보도 파손', relevance: '관련', label: '보도 파손', keywords: '파손', confidence: 82, done: null,
  });
  const empty = toClassifyItem({ id: 8 });
  assert.equal(empty.label, null);
  assert.equal(empty.confidence, null);
  const calls = [];
  const api = createClassifyApi(async (path, opt) => { calls.push([path, opt]); return { available: false, items: [] }; });
  const d = await api.list({ runId: 4 });
  assert.equal(d.available, false);
  assert.equal(calls[0][0], '/api/c08/samples?runId=4');
  await api.mark({ id: 7, result: '맞음', relevance: '관련' });
  assert.deepEqual(calls[1][1].body, { result: '맞음' });
  await api.mark({ id: 7, result: '고침', relevance: '비관련', label: null });
  assert.deepEqual(calls[2][1].body, { result: '고침', relevance: '비관련', label: null });
});

test('회차의 산정 설정 연결: 연결된 것만 번호를 주고, 서버 글자를 주소로 쓰지 않는다', async () => {
  const { toSettingLinks } = await import('../src/api/priority.js');
  assert.deepEqual(toSettingLinks(null), []);
  const l = toSettingLinks({
    weight: { status: 'LINKED', setting_version_id: 52, version_no: 3 },
    threshold: { status: 'UNLINKED', setting_version_id: null },
    priority_condition: { status: 'LINKED', setting_version_id: 9, version_no: null, version_label: '시범' },
  });
  assert.deepEqual(l, [
    { kind: '가중치', id: 52, label: 'v3' },
    { kind: '기준값', id: null, label: null },
    { kind: '우선 확인 조건', id: 9, label: '시범' },
  ]);
});
