import test from 'node:test';
import assert from 'node:assert/strict';

// 시작 주소는 서버 모드 여부에 따라 달라지므로, 환경을 바꿔 모듈을 새로 불러와 확인한다.
async function load(env) {
  const { createServer } = await import('vite');
  const server = await createServer({ configFile: false, envFile: false, logLevel: 'silent', server: { middlewareMode: true }, appType: 'custom', define: Object.fromEntries(Object.entries(env).map(([k, v]) => [`import.meta.env.${k}`, JSON.stringify(v)])) });
  try {
    return { landing: await server.ssrLoadModule('/src/user/features/welcome/landing.js'), close: () => server.close() };
  } catch (e) { await server.close(); throw e; }
}

test('연습용 모드: 운영자는 어드민, 나머지는 점검 후보로 시작한다', async () => {
  const m = await load({});
  try {
    assert.equal(m.landing.startPath('operator'), '/admin');
    assert.equal(m.landing.startPath('district'), '/candidates');
    assert.equal(m.landing.startPath('city'), '/candidates');
  } finally { await m.close(); }
});

test('서버 모드: 역할별 첫 화면을 따른다', async () => {
  const m = await load({ VITE_API_BASE_URL: 'http://127.0.0.1:8000' });
  try {
    assert.equal(m.landing.startPath('district'), '/candidates');
    assert.equal(m.landing.startPath('operator'), '/admin'); // 대시보드(AD-01)가 첫 화면
    assert.equal(m.landing.startPath('city'), '/candidates'); // 메뉴의 첫 화면
  } finally { await m.close(); }
});

test('서버 모드에서 대시보드 연결을 끄면 운영자는 산정 기준, 둘 다 끄면 계정 화면으로 시작한다', async () => {
  const a = await load({ VITE_API_BASE_URL: 'http://x', VITE_OPS_API: 'false' });
  try { assert.equal(a.landing.startPath('operator'), '/admin/standards/criteria'); } finally { await a.close(); }
  const b = await load({ VITE_API_BASE_URL: 'http://x', VITE_OPS_API: 'false', VITE_SETTINGS_API: 'false' });
  try { assert.equal(b.landing.startPath('operator'), '/admin/settings/accounts'); } finally { await b.close(); }
});

test('서버 모드에서 점검 후보가 연결되지 않은 시 도로과는 첫 메뉴인 승인 대기로 시작한다', async () => {
  const m = await load({ VITE_API_BASE_URL: 'http://x', VITE_PRIORITY_API: 'false' });
  try { assert.equal(m.landing.startPath('city'), '/reference/approvals'); } finally { await m.close(); }
});

test('로그인 전에 가려던 주소가 역할에 맞으면 그곳으로, 아니면 첫 화면으로 간다', async () => {
  const m = await load({});
  try {
    assert.equal(m.landing.startPath('district', '/reports/basis'), '/reports/basis');
    assert.equal(m.landing.startPath('operator', '/admin/runs'), '/admin/runs');
    assert.equal(m.landing.startPath('district', '/admin/runs'), '/candidates'); // 사용자 계정은 어드민 주소로 가지 않는다
    assert.equal(m.landing.startPath('operator', '/candidates'), '/admin'); // 운영자는 사용자 주소로 가지 않는다
    assert.equal(m.landing.startPath('district', '/login'), '/candidates');
    assert.equal(m.landing.startPath('district', '//evil.example'), '/candidates');
    assert.equal(m.landing.startPath('district', 'https://evil.example'), '/candidates');
  } finally { await m.close(); }
});

test('소개 모달 열기 규칙: 로그인 전 자동(탭당 한 번), 로그인 후는 메뉴로 연 경우만', async () => {
  const { createServer } = await import('vite');
  const server = await createServer({ configFile: false, envFile: false, logLevel: 'silent', server: { middlewareMode: true }, appType: 'custom' });
  try {
    const { welcomeMode, clampStep } = await server.ssrLoadModule('/src/user/features/welcome/welcomeLogic.js');
    const user = { role: 'district' };
    assert.equal(welcomeMode({ state: null, user: null, pathname: '/login', seenThisTab: false }), 'prelogin');
    assert.equal(welcomeMode({ state: null, user: null, pathname: '/login', seenThisTab: true }), null);
    assert.equal(welcomeMode({ state: null, user: null, pathname: '/candidates', seenThisTab: false }), null);
    assert.equal(welcomeMode({ state: { welcome: true }, user, pathname: '/candidates', seenThisTab: true }), 'replay');
    assert.equal(welcomeMode({ state: null, user, pathname: '/candidates', seenThisTab: false }), null);
    assert.equal(welcomeMode({ state: { welcome: 'yes' }, user, pathname: '/candidates', seenThisTab: false }), null);
    assert.equal(clampStep(-1, 7), 0);
    assert.equal(clampStep(3, 7), 3);
    assert.equal(clampStep(9, 7), 6);
    assert.equal(clampStep(2, 0), 0);
  } finally { await server.close(); }
});
