import test from 'node:test';
import assert from 'node:assert/strict';

async function loadLogic() {
  const { createServer } = await import('vite');
  const server = await createServer({ configFile: false, envFile: false, logLevel: 'silent', server: { middlewareMode: true }, appType: 'custom' });
  try {
    return { logic: await server.ssrLoadModule('/src/shared/guide/guideLogic.js'), config: await server.ssrLoadModule('/src/shared/guide/guideConfig.js'), close: () => server.close() };
  } catch (e) { await server.close(); throw e; }
}

const memoryStorage = () => {
  const m = {};
  return { getItem: (k) => m[k] ?? null, setItem: (k, v) => { m[k] = v; }, removeItem: (k) => { delete m[k]; } };
};

test('역할에 맞는 단계만 남긴다', async () => {
  const { logic, close } = await loadLogic();
  try {
    const steps = [{ title: 'a' }, { title: 'b', roles: ['city'] }, { title: 'c', roles: ['district'] }];
    assert.deepEqual(logic.filterSteps(steps, 'district').map((s) => s.title), ['a', 'c']);
    assert.deepEqual(logic.filterSteps(steps, 'city').map((s) => s.title), ['a', 'b']);
    assert.deepEqual(logic.filterSteps(steps, 'operator').map((s) => s.title), ['a']);
  } finally { await close(); }
});

test('단계 번호는 처음과 끝을 넘지 않는다', async () => {
  const { logic, close } = await loadLogic();
  try {
    assert.equal(logic.clampIndex(-3, 5), 0);
    assert.equal(logic.clampIndex(2, 5), 2);
    assert.equal(logic.clampIndex(8, 5), 4);
    assert.equal(logic.clampIndex(1, 0), 0);
  } finally { await close(); }
});

test('본 화면은 저장하고, 지우면 처음 상태로 돌아간다', async () => {
  const { logic, close } = await loadLogic();
  try {
    const s = memoryStorage();
    assert.equal(logic.hasSeen(s, 'candidates'), false);
    logic.markSeen(s, 'candidates');
    assert.equal(logic.hasSeen(s, 'candidates'), true);
    assert.equal(logic.hasSeen(s, 'annual'), false);
    logic.resetSeen(s);
    assert.equal(logic.hasSeen(s, 'candidates'), false);
  } finally { await close(); }
});

test('저장소를 못 쓰거나 값이 깨져도 오류 없이 본 적 없는 것으로 본다', async () => {
  const { logic, close } = await loadLogic();
  try {
    const broken = { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); }, removeItem: () => { throw new Error('blocked'); } };
    assert.equal(logic.hasSeen(broken, 'x'), false);
    assert.doesNotThrow(() => logic.markSeen(broken, 'x'));
    assert.doesNotThrow(() => logic.resetSeen(broken));
    const garbage = { getItem: () => '{not json', setItem() {}, removeItem() {} };
    assert.equal(logic.hasSeen(garbage, 'x'), false);
  } finally { await close(); }
});

test('안내 카드는 대상 오른쪽 → 왼쪽 → 아래 → 위 순서로 화면 안에 놓인다', async () => {
  const { logic, close } = await loadLogic();
  try {
    const vp = { width: 1000, height: 700 };
    const size = { width: 320, height: 300 };
    assert.equal(logic.placeCoach({ left: 100, top: 100, width: 200, height: 40 }, size, vp).side, 'right');
    assert.equal(logic.placeCoach({ left: 700, top: 100, width: 200, height: 40 }, size, vp).side, 'left');
    assert.equal(logic.placeCoach({ left: 20, top: 20, width: 960, height: 40 }, size, vp).side, 'below');
    assert.equal(logic.placeCoach({ left: 20, top: 600, width: 960, height: 40 }, size, vp).side, 'above');
    const over = logic.placeCoach({ left: 0, top: 0, width: 1000, height: 700 }, size, vp);
    assert.equal(over.side, 'over');
    assert.ok(over.left >= 12 && over.left + size.width <= vp.width - 12);
    assert.ok(over.top >= 12 && over.top + size.height <= vp.height - 12);
  } finally { await close(); }
});

test('화면 주소로 안내 설정을 찾는다', async () => {
  const { logic, config, close } = await loadLogic();
  try {
    assert.equal(logic.findScreen(config.SCREENS, '/candidates')?.key, 'candidates');
    assert.equal(logic.findScreen(config.SCREENS, '/candidates/?x=1')?.key, 'candidates');
    assert.equal(logic.findScreen(config.SCREENS, '/admin')?.key, 'admin-dashboard');
    assert.equal(logic.findScreen(config.SCREENS, '/admin/runs/list')?.key, 'admin-runs');
    assert.equal(logic.findScreen(config.SCREENS, '/reference/data'), null);
  } finally { await close(); }
});

test('안내 설정은 모든 단계가 선택자·장면·제목·설명을 갖고, 역할 이름이 맞다', async () => {
  const { config, close } = await loadLogic();
  try {
    const scenes = new Set(['select', 'menu', 'row', 'button', 'map', 'goto', 'done']);
    const roles = new Set(['district', 'city', 'operator']);
    for (const screen of config.SCREENS) {
      assert.ok(screen.steps.length > 0, screen.key);
      for (const s of screen.steps) {
        assert.ok(s.target && s.title && s.bullets.length > 0, `${screen.key}/${s.title}`);
        assert.ok(scenes.has(s.scene), `${screen.key}/${s.title}: scene`);
        (s.roles || []).forEach((r) => assert.ok(roles.has(r), `${screen.key}/${s.title}: role`));
      }
    }
  } finally { await close(); }
});

test("'로'와 '으로'를 받침에 맞춰 붙인다", async () => {
  const { logic, close } = await loadLogic();
  try {
    assert.equal(logic.josaRo('점검 후보'), '로');
    assert.equal(logic.josaRo('점검 요청서'), '로');
    assert.equal(logic.josaRo('산정 기준'), '으로');
    assert.equal(logic.josaRo('회차 목록'), '으로');
    assert.equal(logic.josaRo('점수 근거'), '로');
    assert.equal(logic.josaRo('서울'), '로'); // ㄹ받침
    assert.equal(logic.josaRo(''), '로');
  } finally { await close(); }
});

test('핵심 경로: 화면의 위치와 다음 화면을 구하고, 열리지 않는 화면은 건너뛴다', async () => {
  const { logic, config, close } = await loadLogic();
  try {
    const all = () => true;
    const op = (key, isOpen = all) => logic.flowInfo(config.FLOWS, config.SCREENS, 'operator', key, isOpen);
    assert.deepEqual(op('admin-dashboard').position, { index: 1, total: 3 });
    assert.equal(op('admin-dashboard').next.key, 'admin-criteria');
    assert.equal(op('admin-runs').next, null);
    assert.equal(op('candidates').position, null); // 운영자 경로 밖
    // 산정 기준이 서버에 연결되지 않은 경우: 대시보드 다음은 회차 목록
    const noCriteria = (p) => p !== '/admin/standards/criteria';
    assert.equal(op('admin-dashboard', noCriteria).next.key, 'admin-runs');
    assert.deepEqual(op('admin-dashboard', noCriteria).position, { index: 1, total: 2 });
    const d = (key) => logic.flowInfo(config.FLOWS, config.SCREENS, 'district', key, all);
    assert.equal(d('candidates').next.key, 'annual');
    assert.equal(d('annual').next, null);
    const c = (key) => logic.flowInfo(config.FLOWS, config.SCREENS, 'city', key, all);
    assert.deepEqual(['candidates', 'approvals', 'conditions'].map((k) => c(k).position.index), [1, 2, 3]);
    assert.equal(c('candidates').next.key, 'approvals');
  } finally { await close(); }
});

test('안내의 마지막 카드: 다음 화면이 있으면 이동 카드, 마지막이면 마침 카드, 경로 밖이면 없음', async () => {
  const { logic, config, close } = await loadLogic();
  try {
    const all = () => true;
    const info = (role, key) => logic.flowInfo(config.FLOWS, config.SCREENS, role, key, all);
    const next = logic.closingStep(info('operator', 'admin-dashboard'), config.GUIDE_COPY);
    assert.equal(next.kind, 'next');
    assert.equal(next.to, '/admin/standards/criteria');
    assert.equal(next.title, '다음은 산정 기준');
    assert.ok(next.target && next.bullets.length > 0);
    const end = logic.closingStep(info('operator', 'admin-runs'), config.GUIDE_COPY);
    assert.equal(end.kind, 'end');
    assert.equal(end.target, null);
    assert.ok(end.bullets[0].includes('대시보드') && end.bullets[0].includes('회차 목록'));
    assert.equal(logic.closingStep(info('operator', 'candidates'), config.GUIDE_COPY), null);
  } finally { await close(); }
});

test('핵심 경로 설정: 모든 화면 키가 실제 화면이고, 이동 주소가 화면 주소와 맞으며, 중복·순환이 없다', async () => {
  const { logic, config, close } = await loadLogic();
  try {
    const keys = new Set(config.SCREENS.map((s) => s.key));
    for (const [role, flow] of Object.entries(config.FLOWS)) {
      assert.equal(new Set(flow).size, flow.length, `${role}: 중복`);
      for (const k of flow) {
        assert.ok(keys.has(k), `${role}/${k}`);
        const screen = config.SCREENS.find((s) => s.key === k);
        assert.ok(screen.path && screen.menuLabel && screen.entry.length > 0 && screen.spotlight, `${k}: 이동 정보`);
        assert.equal(logic.findScreen(config.SCREENS, screen.path)?.key, k, `${k}: path가 자기 화면과 맞아야 함`);
        const mine = screen.steps.some((s) => !s.roles || s.roles.includes(role));
        assert.ok(mine, `${role}/${k}: 이 역할에 보일 단계가 있어야 함`);
      }
    }
  } finally { await close(); }
});

test('화면에 보이는 글에 맥(⌘) 표기가 없다', async () => {
  const { readFile } = await import('node:fs/promises');
  for (const f of ['../src/shared/guide/guideConfig.js', '../src/user/features/candidates/copy.js', '../src/user/features/welcome/copy.js']) {
    const text = await readFile(new URL(f, import.meta.url), 'utf8');
    assert.ok(!/⌘|맥은|command 키/i.test(text), f);
  }
});
