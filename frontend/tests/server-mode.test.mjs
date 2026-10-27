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
