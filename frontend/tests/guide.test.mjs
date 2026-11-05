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
    const scenes = new Set(['select', 'menu', 'row', 'button', 'map']);
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
