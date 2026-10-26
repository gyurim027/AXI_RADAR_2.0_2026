// DOM 상호작용 검증. 실제 DB 시험과 별도이며 브라우저 시각 검증을 대신하지 않는다.
// 선택 실행: RADAR_I07_DOM_RUNTIME=<jsdom 설치 디렉터리> node --test tests/i07-ui.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { build } from 'esbuild';

let JSDOM;
try {
  const require = createRequire(process.env.RADAR_I07_DOM_RUNTIME ? join(process.env.RADAR_I07_DOM_RUNTIME, 'package.json') : import.meta.url);
  ({ JSDOM } = require('jsdom'));
} catch { /* 선택 시험의 의존성이 없으면 명시적으로 건너뛴다 */ }

const liveBase = process.env.RADAR_I07_LIVE_BASE;
const nativeFetch = globalThis.fetch;
if (liveBase) {
  const url = new URL(liveBase);
  assert.ok(['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname));
  assert.equal(process.env.RADAR_I07_LIVE_ISOLATED, '1');
  assert.ok(process.env.RADAR_I07_LIVE_LOGIN?.startsWith('i07_ui_'));
  assert.ok(process.env.RADAR_I07_LIVE_PASSWORD);
}
const cases = liveBase ? ['login_approve'] : ['login_approve', 'approve_apply_failed', 'reject_reason', 'retry_approved', 'nondepartment_content', 'expired_session', 'missing_token'];

test('I-07 기존 화면과 실제 API 어댑터의 DOM 상호작용', { skip: !JSDOM }, async (t) => {
  const folder = await mkdtemp(join(tmpdir(), 'radar-i07-dom-'));
  const bundle = join(folder, 'app.mjs');
  await build({
    stdin: { contents: "import React, {act} from 'react';import {createRoot} from 'react-dom/client';import App from './src/app/App.jsx';export {act};export function mount(node){const root=createRoot(node);root.render(React.createElement(App));return root;}", resolveDir: process.cwd(), loader: 'jsx' },
    outfile: bundle, bundle: true, jsx: 'automatic', format: 'esm', platform: 'browser', loader: { '.css': 'empty', '.svg': 'dataurl' },
    define: { 'import.meta.env': JSON.stringify({ VITE_I07_API: 'true', VITE_API_BASE_URL: liveBase || 'http://i07.test', DEV: false }), 'process.env.NODE_ENV': '"test"' },
    logLevel: 'silent',
  });
  try {
    for (const scenario of cases) await t.test(scenario, async () => {
      const dom = new JSDOM('<!doctype html><html><body><div id="root"></div></body></html>', { url: `http://localhost:5173/${scenario === 'login_approve' ? 'login' : 'reference/approvals'}`, pretendToBeVisual: true });
      globalThis.window = dom.window; globalThis.document = dom.window.document;
      Object.defineProperty(globalThis, 'navigator', { value: dom.window.navigator, configurable: true });
      globalThis.HTMLElement = dom.window.HTMLElement; globalThis.Event = dom.window.Event;
      globalThis.IS_REACT_ACT_ENVIRONMENT = true;
      if (scenario !== 'login_approve') dom.window.sessionStorage.setItem('radar.backend.session.v1', JSON.stringify({ token: scenario === 'missing_token' ? undefined : 'test-token', user: { id: 'city', role: 'city', org: '시험 시 도로과', readOnly: false } }));
      let status = scenario === 'retry_approved' ? '승인' : '제안';
      let applied = false;
      const calls = [];
      const row = () => ({ settingVersionId: 1, settingKind: scenario === 'nondepartment_content' ? '기준값' : '담당 부서 표', versionLabel: '검토안', contentRef: scenario === 'nondepartment_content' ? '검토할 설정 원문' : '보도 파손 담당 부서 수정안', approvalStatus: status, proposedAt: '2026-10-23T11:00:00' });
      globalThis.fetch = async (url, options = {}) => {
        const path = new URL(url).pathname;
        calls.push([path, options.method || 'GET']);
        if (liveBase) return nativeFetch(url, options);
        const ok = (data, code = 200) => new Response(JSON.stringify(data), { status: code, headers: { 'Content-Type': 'application/json' } });
        if (path === '/api/auth/login') return ok({ token: 'test-token', user: { id: 'city', role: 'city', org: '시험 시 도로과', readOnly: false } });
        if (path === '/api/auth/me') return scenario === 'expired_session' ? ok({ error: { code: 'token_expired', message: '다시 로그인해 주세요' } }, 401) : ok({ user: { id: 'city', role: 'city', org: '시험 시 도로과', readOnly: false } });
        if (path === '/api/approvals') return ok({ proposals: status === '제안' ? [row()] : [] });
        if (path === '/api/approvals/unapplied') return ok({ proposals: status === '승인' && !applied ? [row()] : [] });
        if (path.endsWith('/preview')) return ok({ problem: '보도 파손', before: '수정구: 건설과', after: '중원구: 보도팀' });
        if (path.endsWith('/review')) {
          status = JSON.parse(options.body).decision;
          if (scenario === 'approve_apply_failed' && status === '승인') return ok({ error: { status: 409, code: 'table_changed', message: '제안 후 표가 바뀌었습니다', approvalStatus: '승인', departmentApplied: false } }, 409);
          applied = status === '승인';
          return ok({ ok: true, departmentApplied: applied });
        }
        if (path.endsWith('/apply')) { applied = true; return ok({ ok: true, departmentApplied: true }); }
        throw new Error(`승인 화면에서 불필요한 API 호출: ${path}`);
      };
      const { mount, act } = await import(pathToFileURL(bundle).href + '?' + scenario);
      let root;
      const settle = () => act(async () => { await new Promise((r) => setTimeout(r, 10)); });
      const waitFor = async (check) => { for (let i = 0; i < 200; i++) { if (check()) return; await settle(); } assert.ok(check(), document.body.textContent); };
      const findText = (text) => [...document.querySelectorAll('button')].find((el) => el.textContent.trim() === text);
      const click = async (node) => { assert.ok(node, '클릭 대상 필요'); await act(async () => node.click()); await settle(); };
      const fill = async (input, value) => { await act(async () => { Object.getOwnPropertyDescriptor(dom.window.HTMLInputElement.prototype, 'value').set.call(input, value); input.dispatchEvent(new dom.window.Event('input', { bubbles: true })); }); };
      try {
        await act(async () => { root = mount(document.getElementById('root')); }); await settle();
        if (scenario === 'expired_session' || scenario === 'missing_token') {
          await waitFor(() => document.querySelector('input[name="loginId"]'));
          assert.ok(document.querySelector('input[name="loginId"]'));
          if (scenario === 'expired_session') assert.equal(dom.window.sessionStorage.getItem('radar.backend.session.v1'), null);
          if (scenario === 'missing_token') assert.equal(calls.length, 0);
          return;
        }
        if (scenario === 'login_approve') {
          await fill(document.querySelector('input[name="loginId"]'), liveBase ? process.env.RADAR_I07_LIVE_LOGIN : 'city');
          await fill(document.querySelector('input[name="password"]'), liveBase ? process.env.RADAR_I07_LIVE_PASSWORD : 'integration-password');
          await click(findText('로그인'));
        }
        await settle();
        await waitFor(() => /승인 대기/.test(document.body.textContent));
        assert.match(document.body.textContent, /승인 대기/);
        await waitFor(() => document.querySelector('tbody tr'));
        const rowNode = document.querySelector('tbody tr');
        assert.ok(rowNode, document.body.textContent);
        await click(rowNode);
        if (scenario === 'nondepartment_content') {
          assert.match(document.body.textContent, /검토할 설정 원문/);
          assert.ok(!calls.some(([path]) => path.endsWith('/preview')));
        } else if (scenario === 'reject_reason') {
          await click(findText('돌려보내기'));
          await click(findText('보내기'));
          assert.match(document.body.textContent, /사유를 적어/);
          assert.ok(!calls.some(([path]) => path.endsWith('/review')));
          const input = document.querySelector('[role="dialog"] input');
          await fill(input, '근거 보완 요청'); await click(findText('보내기'));
          await waitFor(() => /제안을 돌려보냈습니다/.test(document.body.textContent));
          assert.match(document.body.textContent, /제안을 돌려보냈습니다/);
        } else {
          const buttonText = scenario === 'retry_approved' ? '반영 다시 시도' : '승인하기';
          await waitFor(() => findText(buttonText) && !findText(buttonText).disabled);
          await click(findText(buttonText));
          await waitFor(() => /담당 부서 표 반영을 확인했습니다|승인은 기록됐습니다/.test(document.body.textContent));
          if (scenario === 'approve_apply_failed') {
            assert.match(document.body.textContent, /승인은 기록됐습니다/);
            assert.match(document.body.textContent, /반영되지 않았습니다/);
            assert.match(document.body.textContent, /반영 상태 확인 필요/);
          } else assert.match(document.body.textContent, /담당 부서 표 반영을 확인했습니다/);
        }
        assert.ok(!calls.some(([path]) => path.includes('/priority/') || path.includes('/ops/')));
      } finally {
        if (root) await act(async () => root.unmount());
        dom.window.close();
      }
    });
  } finally { await rm(folder, { recursive: true, force: true }); }
});
