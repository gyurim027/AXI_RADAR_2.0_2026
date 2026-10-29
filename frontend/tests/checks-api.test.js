import test from 'node:test';
import assert from 'node:assert/strict';
import { createBackendClient } from '../src/api/backend.js';
import { createChecksApi } from '../src/api/checks.js';

const response = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const apiWith = (fetchImpl) => createChecksApi(createBackendClient({ baseUrl: 'http://localhost:8000', getToken: () => 'op-token', fetchImpl }));

test('위치 미확인 현황: 상위 곳수를 limit으로 보내고 응답을 그대로 준다', async () => {
  let url;
  const api = apiWith(async (u) => { url = u; return response({ coverage: [{ table: 'src_parking_enforce_place', label: '단속장소', totalRows: 23503, missingRows: 14483, missingRate: 61.6 }], top: { table: 'src_parking_enforce_place', limit: 20, totalMissing: 14483, items: [{ rowKey: 'row_id=1', name: 'OO사거리 앞', enforceCnt: 1520 }] } }); });
  const d = await api.getUnlocated({ limit: 20 });
  assert.equal(url, 'http://localhost:8000/api/ai03/unlocated?limit=20');
  assert.equal(d.coverage[0].missingRate, 61.6);
  assert.equal(d.top.totalMissing, 14483);
});

test('낮음 민원: 접수일·구·동·찾은 방법만 남기고 위치 글자와 좌표는 버린다', async () => {
  let url;
  const api = apiWith(async (u) => { url = u; return response({ total: 390, limit: 1000, offset: 0, complaints: [
    { complaintId: 'C-1', sourceType: '일반 민원', receivedDate: '2025-06-12', locationText: '예시 위치 글자', gu: '분당구', adminDongName: '예시동', gid: 'g', lat: 37.4, lon: 127.1, coordMethod: '주소 변환', coordAccuracy: '낮음', methodKind: '장소' },
    { complaintId: 'C-2', receivedDate: null, gu: null, adminDongName: null, methodKind: null }] }); });
  const d = await api.listLowComplaints({ limit: 1000 });
  assert.equal(url, 'http://localhost:8000/api/ai03/low-complaints?limit=1000&offset=0');
  assert.equal(d.total, 390);
  assert.deepEqual(d.rows[0], { id: 'C-1', date: '2025.06.12', gu: '분당구', dong: '예시동', method: '장소' });
  assert.deepEqual(Object.keys(d.rows[0]).sort(), ['date', 'dong', 'gu', 'id', 'method']);
  assert.deepEqual(d.rows[1], { id: 'C-2', date: null, gu: null, dong: null, method: null });
});

test('낮음 민원: 구를 지정하면 gu를 보낸다', async () => {
  let url;
  const api = apiWith(async (u) => { url = u; return response({ total: 0, complaints: [] }); });
  await api.listLowComplaints({ gu: '수정구', limit: 50 });
  assert.ok(url.includes('gu=%EC%88%98%EC%A0%95%EA%B5%AC'), url);
});
