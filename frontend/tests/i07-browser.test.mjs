// 실제 Chromium의 기존 React 화면 검증. HTTP 응답 제어 시험이며 실제 DB 관통시험과 구분한다.
// 별도 시험 도구 경로만 받는다. 프로젝트 의존성·lockfile·운영 DB를 변경하지 않는다.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {createServer} from 'node:net';
import {mkdir} from 'node:fs/promises';
import {join, resolve} from 'node:path';

const enabled = process.env.RADAR_I07_BROWSER_TEST === '1';
const liveBase=process.env.RADAR_I07_LIVE_BASE;
if(liveBase){
  assert.ok(['127.0.0.1','localhost','[::1]'].includes(new URL(liveBase).hostname));
  assert.equal(process.env.RADAR_I07_LIVE_ISOLATED,'1');
  assert.ok(process.env.RADAR_I07_LIVE_LOGIN?.startsWith('i07_ui_'));
  assert.ok(process.env.RADAR_I07_LIVE_PASSWORD);
}
test('I-07 실제 브라우저 화면', {skip: !enabled, timeout: 120000}, async (t) => {
  const require = createRequire(process.env.RADAR_I07_BROWSER_RUNTIME
    ? resolve(process.env.RADAR_I07_BROWSER_RUNTIME, 'package.json') : import.meta.url);
  const {chromium: playwright} = require('playwright-core');
  const executablePath = process.env.RADAR_I07_CHROMIUM_PATH;
  assert.ok(executablePath,'RADAR_I07_CHROMIUM_PATH에 설치된 Chrome 또는 Chromium 실행 파일을 지정하세요');
  const args = ['--no-sandbox', '--disable-dev-shm-usage'];
  const port = liveBase ? 5173 : await new Promise((res, rej) => {
    const server = createServer(); server.on('error', rej);
    server.listen(0, '127.0.0.1', () => {const p=server.address().port;server.close(() => res(p));});
  });
  const base = `http://127.0.0.1:${port}`;
  const vite = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', String(port), '--strictPort'], {
    cwd: process.cwd(), env: {...process.env, VITE_I07_API:'true', VITE_API_BASE_URL:liveBase||'http://127.0.0.1:49159'}, stdio:'ignore',
  });
  let browser;
  try {
    let ready=false;
    for(let i=0;i<100;i++) {
      if(vite.exitCode !== null) throw new Error(`Vite exited: ${vite.exitCode}`);
      try {if((await fetch(base)).ok){ready=true;break;}}catch{}
      await new Promise(r=>setTimeout(r,100));
    }
    assert.ok(ready,'Vite startup');
    browser=await playwright.launch({executablePath,args,headless:true});
    t.diagnostic(`Browser: ${browser.version()}; ${liveBase?'live isolated API/DB':'API responses are controlled, no DB writes'}`);
    const scenarios=liveBase?['approve']:process.env.RADAR_I07_BROWSER_CASES?.split(',') || ['approve','reject','apply_failed','apply_unknown','retry','preview_failed','session_expired','network_unknown','preview_1280','preview_1024'];
    for(const scenario of scenarios) {
      await t.test(scenario, {todo:scenario==='preview_1024'?'기존 공통 CSS의 최소 폭 1280px로 1024px에서 가로 스크롤 발생. 이번 I-07에서 전역 디자인 변경 안 함':undefined}, async () => {
        const context=await browser.newContext({viewport:{width:scenario==='preview_1024'?1024:scenario==='preview_1280'?1280:1440,height:1000}});
        const page=await context.newPage(); page.setDefaultTimeout(10000);
        const calls=[], errors=[];
        page.on('pageerror', e=>errors.push(e.message));
        let status=scenario==='retry'?'승인':'제안', applied=false;
        const user={id:'city',role:'city',org:'시험 시 도로과',readOnly:false};
        const row=()=>({settingVersionId:1,settingKind:'담당 부서 표',versionLabel:'브라우저 검토안',contentRef:'보도 파손 담당 부서 수정안',approvalStatus:status,proposedAt:'2026-10-23T11:00:00'});
        if(liveBase) page.on('request',request=>{
          if(request.url().startsWith(liveBase+'/api/')&&request.method()!=='OPTIONS') calls.push({path:new URL(request.url()).pathname,method:request.method()});
        });
        else await page.route('http://127.0.0.1:49159/api/**', async route => {
          const request=route.request(), path=new URL(request.url()).pathname;
          calls.push({path,method:request.method(),...(path.endsWith('/review')?{body:request.postDataJSON()}:{} )});
          const respond=(data,code=200)=>route.fulfill({status:code,contentType:'application/json',headers:{'Access-Control-Allow-Origin':base},body:JSON.stringify(data)});
          if(path==='/api/auth/login') return respond({token:'browser-fixture-token',user});
          if(path==='/api/auth/me') return scenario==='session_expired'
            ? respond({error:{code:'token_expired',message:'다시 로그인해 주세요'}},401):respond({user});
          if(path==='/api/approvals') return respond({proposals:status==='제안'?[row()]:[]});
          if(path==='/api/approvals/unapplied') return respond({proposals:status==='승인'&&!applied?[row()]:[]});
          if(path.endsWith('/preview')) return scenario==='preview_failed'
            ? respond({error:{code:'table_changed',message:'제안 후 표가 바뀌었습니다'}},409)
            : respond({problem:'보도 파손',before:'수정구: 건설과',after:'중원구: 보도팀'});
          if(path.endsWith('/review')) {
            status=request.postDataJSON().decision;
            if(status==='승인' && scenario==='network_unknown') return route.abort('failed');
            if(status==='승인' && ['apply_failed','apply_unknown'].includes(scenario)) return respond({error:{
              code:scenario==='apply_failed'?'table_changed':'department_apply_failed',
              message:scenario==='apply_failed'?'제안 후 표가 바뀌었습니다':'부서표 반영 상태를 확인한 뒤 다시 시도하세요',
              approvalStatus:'승인', departmentApplied:scenario==='apply_failed'?false:null,
              applyStatus:scenario==='apply_failed'?'실패':'확인 필요',retryUrl:'/api/approvals/1/apply',
            }},scenario==='apply_failed'?409:503);
            applied=status==='승인';return respond({ok:true,departmentApplied:applied});
          }
          if(path.endsWith('/apply')) {applied=true;return respond({ok:true,departmentApplied:true});}
          errors.push(`Unexpected API: ${path}`);return respond({error:{message:'unexpected API'}},500);
        });
        try {
          if(scenario==='session_expired') await context.addInitScript(({user})=>{
            sessionStorage.setItem('radar.backend.session.v1',JSON.stringify({token:'expired-fixture-token',user}));
          },{user});
          await page.goto(base+(scenario==='session_expired'?'/reference/approvals':'/login'));
          if(scenario==='session_expired') {
            await page.locator('input[name="loginId"]').waitFor();
            assert.equal(await page.evaluate(()=>sessionStorage.getItem('radar.backend.session.v1')),null);
            assert.ok(!calls.some(c=>c.path.includes('/review')));return;
          }
          await page.locator('input[name="loginId"]').fill(liveBase?process.env.RADAR_I07_LIVE_LOGIN:'browser_city');
          await page.locator('input[name="password"]').fill(liveBase?process.env.RADAR_I07_LIVE_PASSWORD:'fixture-only-password');
          await page.getByRole('button',{name:'로그인',exact:true}).click();
          await page.locator('tbody tr').first().click();
          const approve=page.getByRole('button',{name:scenario==='retry'?'담당 부서 표 반영 다시 시도':/승인/}).last();
          if(scenario==='preview_failed') {
            await page.getByRole('alert').filter({hasText:'제안 후 표가 바뀌었습니다'}).waitFor();
            assert.ok(await approve.isDisabled());assert.equal(calls.filter(c=>c.path.endsWith('/review')).length,0);
          } else {
            const comparison=page.locator('section[aria-label="제안 비교"]');
            await comparison.getByText(/수정구: 건설과/).waitFor();
            await comparison.getByText(/중원구: 보도팀/).waitFor();
            assert.ok(await approve.isEnabled());
            const overflow=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));
            if(process.env.RADAR_I07_BROWSER_SCREENSHOTS){
              await mkdir(process.env.RADAR_I07_BROWSER_SCREENSHOTS,{recursive:true});
              await page.screenshot({path:join(process.env.RADAR_I07_BROWSER_SCREENSHOTS,`${scenario}-preview.png`),fullPage:true});
            }
            assert.ok(overflow.scroll<=overflow.width+1,`horizontal overflow: ${JSON.stringify(overflow)}`);
            if(scenario==='preview_1024'||scenario==='preview_1280') return;
            if(scenario==='reject') {
              await page.getByRole('button',{name:'돌려보내기',exact:true}).click();
              const modal=page.getByRole('dialog');await modal.getByRole('button',{name:'보내기',exact:true}).click();
              await modal.getByText(/사유를 적어/).waitFor();
              assert.equal(calls.filter(c=>c.path.endsWith('/review')).length,0);
              await modal.locator('input').fill('근거 보완 요청');
              await modal.getByRole('button',{name:'보내기',exact:true}).click();
              await page.getByText('제안을 돌려보냈습니다.').waitFor();
              assert.deepEqual(calls.find(c=>c.path.endsWith('/review')).body,{decision:'돌려보냄',reviewComment:'근거 보완 요청'});
            } else {
              await approve.click();
              if(scenario==='network_unknown') {
                await page.getByRole('alert').filter({hasText:'처리 상태를 다시 확인'}).waitFor();
              } else if(scenario==='apply_unknown') {
                await page.getByRole('alert').filter({hasText:'승인은 기록됐습니다.'}).waitFor();
                await page.getByText(/반영 여부를 확인해야 합니다/).waitFor();
                assert.equal(await page.getByText('담당 부서 표 반영을 확인했습니다.').count(),0);
              } else if(scenario==='apply_failed') {
                await page.getByRole('alert').filter({hasText:'반영되지 않았습니다'}).waitFor();
                assert.equal(await page.getByText('담당 부서 표 반영을 확인했습니다.').count(),0);
              } else await page.getByText('담당 부서 표 반영을 확인했습니다.').waitFor();
              if(['apply_unknown','apply_failed','network_unknown'].includes(scenario)) await page.getByText(/반영 상태 확인 필요/).waitFor();
              assert.equal(calls.filter(c=>c.path.endsWith(scenario==='retry'?'/apply':'/review')).length,1);
            }
          }
          assert.deepEqual(errors,[]);
          assert.ok(!calls.some(c=>c.path.includes('/priority/')||c.path.includes('/ops/')));
          if(process.env.RADAR_I07_BROWSER_SCREENSHOTS) await page.screenshot({path:join(process.env.RADAR_I07_BROWSER_SCREENSHOTS,`${scenario}-result.png`),fullPage:true});
        } catch(error) {
          t.diagnostic(`${scenario}: ${error.message}; page=${(await page.locator('body').innerText()).slice(0,1600)}; calls=${JSON.stringify(calls)}`);
          throw error;
        } finally {await context.close();}
      });
    }
  } finally {
    if(browser) await browser.close();
    vite.kill('SIGTERM');
    if(vite.exitCode===null) await new Promise(res=>{vite.once('exit',res);setTimeout(()=>{vite.kill('SIGKILL');res();},2000).unref();});
  }
});
