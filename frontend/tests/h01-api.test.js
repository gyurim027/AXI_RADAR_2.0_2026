import test from 'node:test';
import assert from 'node:assert/strict';
import { createBackendClient } from '../src/api/backend.js';
import { createH01Api, toAnnualPreview } from '../src/api/h01.js';
import { snakeKeys } from '../src/api/caseKeys.js';

const response = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const apiWith = (fetchImpl) => createH01Api(createBackendClient({ baseUrl: 'http://localhost:8000', getToken: () => 't', fetchImpl }));

// 진이님이 준 최종 응답(확정 후 200). 서버는 camelCase로 준다.
const OK = {
  runId: 2,
  roundFinalized: true,
  districtConfirmations: [{ gu: '수정구', done: true }],
  candidateCount: 1,
  groups: [
    {
      department: '담당 부서 확인 필요',
      candidates: [
        {
          gid: '다사67ba38aa',
          gu: '수정구',
          score: 78.1259,
          rankNo: 3,
          address: '경기도 성남시 수정구 수정로135번길 5-1 (태평동)',
          addressSource: '보호구역 시설',
          landmark: '보호구역 인근',
          landmarkSource: '보호구역 시설',
          departmentStatus: '확인 필요',
          departmentReason: '산정 지표와 담당 부서 문제 유형 간 확정 연결 및 F-02 도로 종류 입력이 없습니다.',
          dataAsOf: null,
          evidence: [
            { indicatorCode: 'exp_board_alight_daily_avg', indicatorName: '정류소 일평균 승하차량 합계', scoreContribution: 19.271523 },
            { indicatorCode: 'vul_zone_total', indicatorName: '보호구역 중첩 수', scoreContribution: 12.329545 },
            { indicatorCode: 'res_hotspot_cnt', indicatorName: '사고다발지 자료 행 수', scoreContribution: 9.91404 },
          ],
          evidenceStatus: '저장된 실제 점수 기여값 기준',
          requestText: '해당 구역의 점수 산정에서 정류소 일평균 승하차량 합계, 보호구역 중첩 수, 사고다발지 자료 행 수 관련 지표가 주요 기여 항목으로 확인되었습니다. 현장 점검 및 필요한 조치 검토를 요청합니다.',
          requestTextSource: 'H01_STORED_SCORE_TEMPLATE',
        },
      ],
    },
  ],
  previewOnly: true,
  storage: 'development_memory_only',
  operationalSaved: false,
  automaticSend: false,
  readyForOfficialExport: false,
  limitations: ['G-03/G-06 개발용 메모리 기록 사용', '담당 부서는 미확정일 수 있음'],
};

test('확정 후 응답을 화면 모양으로 바꾼다(진이님 응답 그대로)', async () => {
  const urls = [];
  const api = apiWith(async (url) => { urls.push(url); return response(OK); });
  const r = await api.getPreview({ runId: '2' });
  assert.equal(urls[0], 'http://localhost:8000/api/h01/runs/2/preview');
  assert.equal(r.ready, true);
  assert.equal(r.preview, true);
  assert.equal(r.count, 1);
  assert.deepEqual(r.rows, [{ dept: '담당 부서 확인 필요', count: 1 }]);
  const c = r.groups[0].candidates[0];
  assert.equal(c.rank, 3);
  assert.equal(c.score, 78.1);
  assert.equal(c.address, '경기도 성남시 수정구 수정로135번길 5-1 (태평동)');
  assert.equal(c.landmark, '보호구역 인근');
  assert.deepEqual(c.evidence, ['정류소 일평균 승하차량 합계', '보호구역 중첩 수', '사고다발지 자료 행 수']);
  assert.match(c.requestText, /점검 및 필요한 조치 검토를 요청합니다/);
  assert.equal(c.dataAsOf, null); // 연결되기 전에는 비워 두고, 화면이 '확인 필요'로 보인다
});

test('내부 구분 값과 한계 문구는 화면 모양에 넣지 않는다', () => {
  const r = toAnnualPreview(snakeKeys(OK));
  const text = JSON.stringify(r);
  assert.equal(text.includes('development_memory_only'), false);
  assert.equal(text.includes('개발용'), false);
  assert.equal(text.includes('F-02'), false); // 담당 부서 이유의 내부 용어도 가져오지 않는다
});

test('우선 점검 대상이 없으면 부서 묶음이 비고 확정 상태는 그대로다', async () => {
  const api = apiWith(async () => response({ ...OK, candidateCount: 0, groups: [] }));
  const r = await api.getPreview({ runId: 2 });
  assert.equal(r.ready, true);
  assert.deepEqual(r.groups, []);
  assert.equal(r.count, 0);
});

test('회차가 확정되기 전(409 ERR-45)이면 만들 수 없는 상태로 돌려준다', async () => {
  const api = apiWith(async () => response({ error: { status: 409, code: 'ERR-45', message: '우선 점검 대상을 확정한 뒤 만들 수 있습니다.' } }, 409));
  const r = await api.getPreview({ runId: 2 });
  assert.equal(r.ready, false);
  assert.deepEqual(r.groups, []);
});

test('다른 오류는 그대로 던진다(오류 화면으로 이어진다)', async () => {
  const api409other = apiWith(async () => response({ error: { status: 409, code: 'OTHER', message: '다른 충돌' } }, 409));
  await assert.rejects(() => api409other.getPreview({ runId: 2 }), (e) => e.status === 409 && e.code === 'OTHER');
  const api403 = apiWith(async () => response({ error: { status: 403, code: 'forbidden', message: '권한이 없습니다.' } }, 403));
  await assert.rejects(() => api403.getPreview({ runId: 2 }), (e) => e.status === 403);
  const api500 = apiWith(async () => response({ error: { status: 500, code: 'server_error', message: '오류' } }, 500));
  await assert.rejects(() => api500.getPreview({ runId: 2 }), (e) => e.status === 500);
});

test('출처를 모르는 대표 지점 이름은 보이지 않고, 값이 없으면 비워 둔다', () => {
  const base = OK.groups[0].candidates[0];
  const r = toAnnualPreview(snakeKeys({ ...OK, groups: [{ department: '담당 부서 확인 필요', candidates: [{ ...base, landmark: '해님 어린이집', landmarkSource: '알 수 없음', addressSource: null }, { ...base, gid: 'b', address: null, landmark: null, landmarkSource: null, addressSource: null, evidence: [], requestText: null, score: null, rankNo: null }] }] }));
  const [a, b] = r.groups[0].candidates;
  assert.equal(a.landmark, null);
  assert.equal(b.address, null);
  assert.equal(b.score, null);
  assert.equal(b.rank, null);
  assert.deepEqual(b.evidence, []);
  assert.equal(b.requestText, '');
});

test('부서 이름이 비어 있으면 담당 부서 확인 필요로 부른다', () => {
  const r = toAnnualPreview(snakeKeys({ ...OK, groups: [{ department: '', candidates: [OK.groups[0].candidates[0]] }] }));
  assert.equal(r.groups[0].dept, '담당 부서 확인 필요');
});
