// I-02 기존 운영자 화면의 실제 브라우저 검증. live 모드는 격리 시험 실행기만 사용한다.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {spawn} from 'node:child_process';
import {createServer} from 'node:net';
import {mkdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';

const live=process.env.RADAR_I07_LIVE_BASE;
if(live){
  assert.equal(process.env.RADAR_I07_LIVE_ISOLATED,'1');
  assert.ok(['127.0.0.1','localhost','[::1]'].includes(new URL(live).hostname));
  assert.ok(process.env.RADAR_I07_LIVE_LOGIN?.startsWith('i07_ui_'));
  assert.ok(process.env.RADAR_I07_LIVE_PASSWORD);
}
test('I-02 운영자 조회와 I-07 권한 분리', {skip:process.env.RADAR_I02_BROWSER_TEST!=='1',timeout:120000},async t=>{
  const require=createRequire(resolve(process.env.RADAR_I07_BROWSER_RUNTIME||'.','package.json'));
  const {chromium}=require('playwright-core');
  assert.ok(process.env.RADAR_I07_CHROMIUM_PATH);
  const port=live?5173:await new Promise((res,rej)=>{const s=createServer();s.on('error',rej);s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>res(p));});});
  const base=`http://127.0.0.1:${port}`,api=live||'http://127.0.0.1:49158';
  const vite=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(port),'--strictPort'],{cwd:process.cwd(),env:{...process.env,VITE_I07_API:'true',VITE_SETTINGS_API:'true',VITE_API_BASE_URL:api},stdio:'ignore'});
  let browser;
  try{
    let ready=false;for(let i=0;i<100;i++){if(vite.exitCode!==null)throw new Error('Vite startup failed');try{if((await fetch(base)).ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}
    assert.ok(ready);browser=await chromium.launch({executablePath:process.env.RADAR_I07_CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage'],headless:true});
    t.diagnostic(`Browser ${browser.version()}; ${live?'actual isolated HTTP/DB':'controlled API responses'}`);
    const cases=live?['operator_city_operator']:['list_detail','filters_empty','query_error','expired_session','wrong_role'];
    for(const scenario of cases)await t.test(scenario,async()=>{
      const ctx=await browser.newContext({viewport:{width:1440,height:1000}}),page=await ctx.newPage();page.setDefaultTimeout(10000);
      const calls=[],errors=[];page.on('pageerror',e=>errors.push(e.message));
      const operator={id:'operator',role:'operator',org:'운영자 조회 시험',readOnly:false};
      const raw='<script>window.i02Unsafe=true</script> 설정 원문 또는 파일 위치';
      const rows=[{settingVersionId:2,settingKind:'가중치',versionLabel:'I02 연결 확인',contentRef:raw,approvalStatus:'제안',proposedBy:7,proposedAt:'2026-10-23T10:00:00',approvedBy:null,approvedAt:null,reviewComment:null},
        {settingVersionId:3,settingKind:'기준값',versionLabel:'I02 연결 확인',contentRef:null,approvalStatus:'돌려보냄',proposedBy:7,reviewComment:'근거 보완 요청',approvedBy:22}];
      if(live)page.on('request',r=>{if(r.url().startsWith(api+'/api/')&&r.method()!=='OPTIONS')calls.push(new URL(r.url()).pathname);});
      else await page.route(api+'/api/**',async route=>{
        const u=new URL(route.request().url());calls.push(u.pathname);
        const reply=(data,status=200)=>route.fulfill({status,contentType:'application/json',headers:{'Access-Control-Allow-Origin':base},body:JSON.stringify(data)});
        if(u.pathname==='/api/auth/login')return reply({token:'operator-fixture',user:scenario==='wrong_role'?{...operator,role:'district'}:operator});
        if(u.pathname==='/api/auth/me')return scenario==='expired_session'?reply({error:{code:'token_expired',message:'다시 로그인해 주세요'}},401):reply({user:operator});
        if(u.pathname==='/api/settings/versions'){
          if(scenario==='query_error')return reply({error:{code:'query_failed',message:'설정 조회 시험 오류'}},500);
          return reply({versions:rows.filter(r=>(!u.searchParams.get('kind')||r.settingKind===u.searchParams.get('kind'))&&(!u.searchParams.get('status')||r.approvalStatus===u.searchParams.get('status'))),hasMore:false,limit:100,offset:0});
        }
        if(u.pathname.startsWith('/api/settings/versions/'))return reply(rows.find(r=>String(r.settingVersionId)===u.pathname.split('/').at(-1)));
        errors.push(`Unexpected API ${u.pathname}`);return reply({error:{message:'unexpected API'}},500);
      });
      async function login(p,id,password){await p.goto(base+'/login');await p.locator('input[name="loginId"]').fill(id);await p.locator('input[name="password"]').fill(password);await p.getByRole('button',{name:'로그인',exact:true}).click();}
      async function capture(name){if(process.env.RADAR_I07_BROWSER_SCREENSHOTS){await mkdir(process.env.RADAR_I07_BROWSER_SCREENSHOTS,{recursive:true});await page.screenshot({path:join(process.env.RADAR_I07_BROWSER_SCREENSHOTS,`i02-${name}.png`),fullPage:true});}}
      try{
        if(scenario==='expired_session'){
          await ctx.addInitScript(user=>sessionStorage.setItem('radar.backend.session.v1',JSON.stringify({token:'expired',user})),operator);
          await page.goto(base+'/admin/standards/criteria');await page.locator('input[name="loginId"]').waitFor();
          assert.equal(await page.evaluate(()=>sessionStorage.getItem('radar.backend.session.v1')),null);return;
        }
        await login(page,live?'i07_ui_operator':'operator',live?process.env.RADAR_I07_LIVE_PASSWORD:'fixture-only');
        if(scenario==='wrong_role'){await page.getByRole('alert').filter({hasText:'계정으로 접속'}).waitFor();assert.equal(calls.filter(p=>p.includes('/settings/')).length,0);return;}
        if(scenario==='query_error'){await page.getByRole('alert').filter({hasText:'설정 조회 시험 오류'}).waitFor();assert.equal(await page.getByText('조건에 맞는 저장된 설정이 없습니다.').count(),0);await capture('query-error');return;}
        await page.getByRole('table',{name:'저장된 산정 설정'}).waitFor();
        assert.equal(await page.getByRole('button',{name:'새 버전',exact:true}).count(),0);
        if(scenario==='filters_empty'){
          await page.getByLabel('처리 상태',{exact:true}).selectOption('승인');await page.getByText('조건에 맞는 저장된 설정이 없습니다.').waitFor();return;
        }
        await page.getByRole('row').filter({hasText:/가중치.*I02 연결 확인/}).click();
        await page.getByRole('table',{name:'설정과 승인 기록'}).waitFor();
        await page.getByRole('row').filter({hasText:'설정 번호'}).filter({hasText:'2'}).waitFor();
        if(!live){
          assert.equal(await page.locator('pre').textContent(),raw);assert.equal(await page.evaluate(()=>window.i02Unsafe),undefined);
          await capture('detail');await page.getByRole('link',{name:'산정 기준 목록',exact:true}).click();
          await page.getByRole('row').filter({hasText:/기준값.*I02 연결 확인/}).click();
          await page.getByRole('row').filter({hasText:'검토 의견'}).filter({hasText:'근거 보완 요청'}).waitFor();
        }else{
          await capture('live-before-review');
          const cityCtx=await browser.newContext({viewport:{width:1440,height:1000}});
          try{
            const city=await cityCtx.newPage();city.setDefaultTimeout(10000);
            await login(city,process.env.RADAR_I07_LIVE_LOGIN,process.env.RADAR_I07_LIVE_PASSWORD);
            await city.getByRole('row').filter({hasText:/가중치.*I02 연결 확인/}).click();
            await city.getByRole('button',{name:/가중치 수정 제안 승인하기/}).click();
            await city.getByText('승인을 기록했습니다. 산정은 별도로 실행합니다.').waitFor();
          }finally{await cityCtx.close();}
          await page.getByRole('button',{name:'새로고침',exact:true}).click();
          await page.getByRole('row').filter({hasText:'처리 상태'}).filter({hasText:'승인'}).waitFor();
          await page.getByRole('row').filter({hasText:'처리자 번호'}).filter({hasText:'22'}).waitFor();
          await capture('live-after-review');
        }
        assert.deepEqual(errors,[]);assert.ok(!calls.some(p=>p.includes('/priority/')||p.includes('/ops/')));
        assert.ok((await page.evaluate(()=>document.documentElement.scrollWidth))<=1441);
      }catch(e){t.diagnostic(`${scenario}: ${e.message}; body=${(await page.locator('body').innerText()).slice(0,1500)}; calls=${JSON.stringify(calls)}`);throw e;}
      finally{await ctx.close();}
    });
  }finally{if(browser)await browser.close();vite.kill('SIGTERM');if(vite.exitCode===null)await new Promise(res=>{vite.once('exit',res);setTimeout(()=>{vite.kill('SIGKILL');res();},2000).unref();});}
});
