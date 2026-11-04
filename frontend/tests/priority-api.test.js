import test from 'node:test';
import assert from 'node:assert/strict';
import { createBackendClient } from '../src/api/backend.js';
import { createPriorityApi, toRun, toCandidateList, toCandidateDetail, toConditionRecord, toAdminRun, cellBounds } from '../src/api/priority.js';
import { RUN_STATUS } from '../src/shared/constants.js';

const response = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const apiWith = (fetchImpl) => createPriorityApi(createBackendClient({ baseUrl: 'http://localhost:8000', getToken: () => 't', fetchImpl }));
const GUS = ['수정구', '중원구', '분당구'];
const ALL = '3개 구 전체';

const run2 = { run_id: 2, rule_version: 'X', setting_version_display: null };
const cand = (gid, gu, score, rank, extra = {}) => ({
  run_id: 2, gid, gu, center_lat: 37.4, center_lon: 127.1, score, rank_no: rank, matched_roles: '', complaint_cnt: 3,
  details: {
    confidence_grade: 'MEDIUM',
    indicator_contributions: { cond_blind_spot_cnt: 10, cond_pothole_detect_cnt: 20, cond_obstacle_cnt: null, vul_zone_total: 5 },
    unevaluated_reasons: { cond_obstacle_cnt: 'OUTSIDE_SURVEY_SCOPE', exp_board_alight_daily_avg: 'NO_RECORD_COVERAGE_UNKNOWN' },
  },
  ...extra,
});

test('회차: 서버가 상태·이름을 주지 않으면 가짜로 채우지 않고 상태 정보 없음으로 둔다', () => {
  const r = toRun(run2);
  assert.equal(r.id, '2');
  assert.equal(r.status, RUN_STATUS.UNKNOWN);
  assert.equal(r.name, '회차 2');
  assert.equal(r.version, null);
});

test('회차: 서버가 상태·이름·종류를 주면 그대로 쓴다', () => {
  const r = toRun({ run_id: 3, status: '검토 중', name: '2027 연간', kind: '연간', opened_at: '2026-11-04' });
  assert.equal(r.status, RUN_STATUS.REVIEW);
  assert.equal(r.name, '2027 연간');
  assert.equal(r.kind, 'annual');
  assert.equal(toRun({ run_id: 4, status: '참고', kind: '반기 참고' }).kind, 'ref');
});

test('회차 목록: 서버가 camelCase로 준 응답을 읽고 보존 대상 1회차는 뺀다', async () => {
  const api = apiWith(async () => response({ runs: [{ runId: 2, settingVersionDisplay: null }, { runId: 1 }] }));
  const runs = await api.listRuns();
  assert.deepEqual(runs.map((r) => r.id), ['2']);
});

test('후보 목록: 점수 순으로 구 안 순위를 다시 매기고 구 도로관리팀은 자기 구만 본다', () => {
  const res = { run: run2, candidates: [cand('a', '수정구', 50, 3), cand('b', '분당구', 90, 1), cand('c', '수정구', 70, 2), cand('d', null, 10, 4)] };
  const d = toCandidateList(res, { role: 'district', gu: '수정구' }, { gu: null, guList: GUS, allGu: ALL });
  assert.deepEqual(d.items.map((r) => [r.gid, r.rank]), [['c', 1], ['a', 2]]);
  assert.equal(d.counts.total, 2);
  assert.equal(d.counts.none, 2);
  const city = toCandidateList(res, { role: 'city' }, { gu: null, guList: GUS, allGu: ALL });
  assert.deepEqual(city.items.map((r) => r.gid), ['b', 'c', 'a']);
  const one = toCandidateList(res, { role: 'city' }, { gu: '분당구', guList: GUS, allGu: ALL });
  assert.deepEqual(one.items.map((r) => r.gid), ['b']);
});

test('후보 행: 서버에 없는 주소·대표 지점은 비워 두고, 신뢰도·방해요소·평가하지 못한 분야는 서버 값으로 만든다', () => {
  const d = toCandidateList({ run: run2, candidates: [cand('a', '수정구', 50, 1)] }, { role: 'city' }, { gu: null, guList: GUS, allGu: ALL });
  const row = d.items[0];
  assert.equal(row.address, null);
  assert.equal(row.landmark, null);
  assert.equal(row.reliability, '보통');
  assert.deepEqual(row.obstacleNames, ['포트홀', '사각지대']); // 기여가 큰 순서, 기여 없는 것은 뺀다
  assert.equal(row.obstacleMain, '포트홀');
  assert.equal(row.obstacleRest, 1);
  assert.deepEqual(row.unratedNames, ['노출']); // 노출은 지표 하나가 모두 비어 분야 전체가 비었다
  assert.equal(row.decision, '결정 전');
  assert.deepEqual(row.bounds, cellBounds(37.4, 127.1));
});

test('격자 칸은 중심에서 반 칸(250m)씩 떨어진 사각형이다', () => {
  const [[s, w], [n, e]] = cellBounds(37.4, 127.1);
  assert.ok(Math.abs((n - s) * 111320 - 250.9) < 1);
  assert.ok(Math.abs((e - w) * 111320 * Math.cos((37.4 * Math.PI) / 180) - 250) < 2);
});

test('후보 상세: 중심 좌표는 목록에서 받은 값을 쓰고, 담당 부서가 없으면 null이다', () => {
  const list = toCandidateList({ run: run2, candidates: [cand('a', '수정구', 50, 1)] }, { role: 'city' }, { gu: null, guList: GUS, allGu: ALL });
  const detail = toCandidateDetail({ ...cand('a', '수정구', 50, 1), center_lat: null, center_lon: null, explanation_context: { summary: '요약 문장' } }, { list, user: { org: '시 도로과' } });
  assert.deepEqual(detail.bounds, cellBounds(37.4, 127.1));
  assert.equal(detail.dept, null);
  assert.equal(detail.explanation, '요약 문장');
  assert.equal(detail.evidence[0].item, '포트홀 탐지 건수'); // 근거 표에는 정식 표시 이름을 쓴다
  assert.equal(detail.canDecide, false);
});

test('후보 상세: 서버가 담당 부서를 주면 이름과 확실도를 쓴다', () => {
  const detail = toCandidateDetail({ ...cand('a', '수정구', 50, 1), department: { name: '수정구 도로관리팀', confidence: '확인됨', reason: '일반도로' } }, { list: null, user: {} });
  assert.deepEqual(detail.dept, { name: '수정구 도로관리팀', contact: null, status: '확인됨' });
});

test('후보 목록·상세: 서버가 camelCase로 준 응답(지표 코드 키 포함)도 읽는다', async () => {
  const calls = [];
  const api = apiWith(async (url) => {
    calls.push(url);
    if (url.includes('/candidates/')) {
      return response({ runId: 2, gid: 'a', gu: '수정구', score: 50, rankNo: 1, conditions: { result: 'Y', hazard: 'Y', exposure: 'N', vulnerable: null }, complaintCnt: 3,
        details: { confidenceGrade: 'HIGH', indicatorContributions: { condPotholeDetectCnt: 20 }, unevaluatedReasons: {} },
        explanationContext: { summary: '요약' } });
    }
    return response({ run: { runId: 2 }, total: 1, candidates: [{ runId: 2, gid: 'a', gu: '수정구', centerLat: 37.4, centerLon: 127.1, score: 50, rankNo: 1, conditions: { result: 'Y', hazard: 'Y', exposure: 'N', vulnerable: null },
      details: { confidenceGrade: 'HIGH', indicatorContributions: { condPotholeDetectCnt: 20, condBlindSpotCnt: 5 }, unevaluatedReasons: { expBoardAlightDailyAvg: 'OUTSIDE_SURVEY_SCOPE' } } }] });
  });
  const user = { role: 'city', org: '시' };
  const list = await api.listCandidates({ runId: '2', gu: null, user, guList: GUS, allGu: ALL });
  assert.equal(calls[0], 'http://localhost:8000/api/priority/runs/2/candidates?limit=3000');
  assert.equal(list.run.id, '2');
  assert.equal(list.items[0].reliability, '높음');
  assert.deepEqual(list.items[0].obstacleNames, ['포트홀', '사각지대']);
  assert.deepEqual(list.items[0].unratedNames, ['노출']);
  assert.deepEqual(list.items[0].conditions, ['result', 'hazard']);
  assert.ok(list.items[0].bounds);
  const detail = await api.getCandidateDetail({ runId: '2', gid: 'a', user });
  assert.equal(detail.evidence[0].item, '포트홀 탐지 건수');
  assert.equal(detail.explanation, '요약');
  assert.deepEqual(detail.bounds, list.items[0].bounds);
});

test('우선 확인 조건: 4개를 Y·N·NULL로 구분하고 NULL을 미충족으로 바꾸지 않는다', () => {
  const c = (conditions) => toCandidateList({ run: run2, candidates: [cand('a', '수정구', 50, 1, { conditions })] }, { role: 'city' }, { gu: null, guList: GUS, allGu: ALL }).items[0];
  const row = c({ result: 'Y', hazard: 'Y', exposure: 'N', vulnerable: null });
  assert.deepEqual(row.conditionStates.map((s) => [s.id, s.state]), [['result', 'Y'], ['hazard', 'Y'], ['exposure', 'N'], ['vulnerable', 'NULL']]);
  assert.deepEqual(row.conditions, ['result', 'hazard']); // 맞은 조건만. 미평가는 맞은 것이 아니다
  assert.deepEqual(c({ result: 'N', hazard: 'Y', exposure: null, vulnerable: 'N' }).conditions, []); // 종합이 Y가 아니면 우선 확인 후보가 아니다
  assert.deepEqual(c({ result: null, hazard: null, exposure: null, vulnerable: null }).conditions, []);
  assert.equal(c({ result: null }).conditionStates[0].state, 'NULL');
});

test('조건 충족과 후보 선정은 다른 값이다: 종합이 Y여도 선정 여부는 건드리지 않는다', () => {
  const d = toCandidateList({ run: run2, candidates: [cand('a', '수정구', 10, 5, { conditions: { result: 'Y' }, selected_yn: 'N' })] }, { role: 'city' }, { gu: null, guList: GUS, allGu: ALL });
  assert.equal(d.items[0].conditions.includes('result'), true);
  assert.equal(d.items[0]._server.rankNo, 5);
});

test('미평가 사유: 뜻을 풀어 쓴다', () => {
  const d = toCandidateList({ run: run2, candidates: [cand('a', '수정구', 50, 1, { details: { confidence_grade: 'LOW', indicator_contributions: {}, unevaluated_reasons: { exp_board_alight_daily_avg: 'NO_RECORD_COVERAGE_UNKNOWN', vul_zone_total: 'OUTSIDE_SURVEY_SCOPE' } } })] }, { role: 'city' }, { gu: null, guList: GUS, allGu: ALL });
  const detail = toCandidateDetail({ ...cand('a', '수정구', 50, 1), details: { confidence_grade: 'LOW', indicator_contributions: {}, unevaluated_reasons: { exp_board_alight_daily_avg: 'NO_RECORD_COVERAGE_UNKNOWN', vul_zone_total: 'OUTSIDE_SURVEY_SCOPE' } } }, { list: d, user: {} });
  assert.deepEqual(detail.unrated.map((u) => [u.name, u.reason]), [['노출', '탐지 기록이 없고 관측 범위를 확인할 수 없음'], ['취약', '장애물 조사 범위 밖']]);
  assert.equal(detail.reliability, '낮음');
});

const dist = { role: 'district', gu: '수정구', org: '수정구 도로관리팀' };
const open_ = { ...run2, status: '검토 중' };
const list2 = (user, extra = {}, candidates = [cand('a', '수정구', 70, 1), cand('b', '수정구', 60, 2), cand('c', '수정구', 50, 3)]) =>
  toCandidateList({ run: open_, candidates }, user, { gu: null, guList: GUS, allGu: ALL, ...extra });

test('결정 목록: 서버가 준 결정을 후보에 합치고 결정 현황 숫자를 센다', () => {
  const d = list2(dist, { myConfirm: { gu: '수정구', done: false, date: null }, decisions: [{ gid: 'a', decision: '우선 점검 대상' }, { gid: 'b', decision: '보류', reason_code: '추가 확인 필요' }] });
  assert.deepEqual(d.items.map((r) => [r.gid, r.decision]), [['a', '우선 점검 대상'], ['b', '보류'], ['c', '결정 전']]);
  assert.deepEqual(d.counts, { total: 3, none: 1, target: 1, exclude: 0, hold: 1 });
});

test('결정 목록이 없으면(null) 전부 결정 전이다', () => {
  const d = list2(dist, { decisions: null });
  assert.equal(d.counts.none, 3);
});

test('결정 버튼은 구 도로관리팀 · 검토 중 회차 · 자기 구 확정 전에만 열린다', () => {
  const ok = { myConfirm: { gu: '수정구', done: false, date: null } };
  assert.equal(list2(dist, ok).canDecide, true);
  assert.equal(list2(dist, { myConfirm: { gu: '수정구', done: true, date: null } }).canDecide, false); // 이미 확정
  assert.equal(list2({ ...dist, readOnly: true }, ok).canDecide, false); // 보기 전용
  assert.equal(list2({ role: 'city' }, ok).canDecide, false); // 시 도로과는 결정하지 않는다
  const unknown = toCandidateList({ run: run2, candidates: [cand('a', '수정구', 70, 1)] }, dist, { gu: null, guList: GUS, allGu: ALL, myConfirm: ok.myConfirm });
  assert.equal(unknown.canDecide, false); // 상태 정보 없음
});

test('회차 상태: 서버가 상태를 주지 않아도 3개 구가 모두 확정했으면 확정이다', () => {
  assert.equal(toRun(run2, { finalized: true }).status, '확정');
  assert.equal(toRun(run2, { finalized: false }).status, '상태 정보 없음');
  assert.equal(toRun({ ...run2, status: '산정 중' }, { finalized: true }).status, '산정 중'); // 산정 중 회차는 서버 상태가 우선
});

test('회차 목록: 상태가 없거나 검토 중인 회차만 확정 여부를 묻는다', async () => {
  const asked = [];
  const api = apiWith(async () => response({ runs: [{ runId: 2 }, { runId: 3, status: '검토 중' }, { runId: 4, status: '참고' }, { runId: 1 }] }));
  const runs = await api.listRuns({ finalizedOf: async (id) => { asked.push(id); return true; } });
  assert.deepEqual(asked, [2, 3]);
  assert.deepEqual(runs.map((r) => [r.id, r.status]), [['2', '확정'], ['3', '확정'], ['4', '참고']]);
});

test('후보 상세: 결정 기록과 결정 탭 표시', () => {
  const list = list2(dist, { myConfirm: { gu: '수정구', done: false, date: null } });
  const d = toCandidateDetail(cand('a', '수정구', 70, 1), { list, user: dist, record: { decision: '우선 점검 대상', memo: '메모' } });
  assert.equal(d.decision, '우선 점검 대상');
  assert.equal(d.showDecisionTab, true);
  assert.equal(d.showRequest, true);
  assert.equal(d.memo, '메모');
  assert.equal(d.canDecide, true);
});

test('점수 근거: 회차가 확정이 아니면 준비되지 않았다', () => {
  const list = toCandidateList({ run: { ...run2, status: '검토 중' }, candidates: [cand('a', '수정구', 70, 1)] }, { role: 'city' }, { gu: null, guList: GUS, allGu: ALL });
  const r = toConditionRecord(list);
  assert.equal(r.ready, false);
  assert.equal(r.server, true);
});

test('점수 근거: 확정 회차에서 후보 수·우선 확인 후보 수·분야별 미평가 후보 수를 센다', () => {
  const withCond = (gid, result) => cand(gid, '수정구', 50, 1, { conditions: { result, hazard: result, exposure: 'N', vulnerable: null } });
  const list = toCandidateList({ run: { ...run2, status: '확정' }, candidates: [withCond('a', 'Y'), withCond('b', 'N'), withCond('c', null)] }, { role: 'city' }, { gu: null, guList: GUS, allGu: ALL });
  const r = toConditionRecord(list);
  assert.equal(r.ready, true);
  assert.equal(r.candidateCount, 3);
  assert.equal(r.priorityCount, 1); // 종합이 충족인 후보만
  assert.equal(r.unrated.find((u) => u.name === '노출').count, 3); // cand 기본값: 노출 지표 하나가 모두 비어 있음
  assert.equal(r.dataCount, null); // 서버에 없는 값은 비워 둔다
  assert.equal(r.version, null);
  assert.equal(r.indicators.length, 9);
});

test('어드민 회차 한 줄: 서버가 주지 않는 값은 -로 두고 상태는 상태 정보 없음', () => {
  const row = toAdminRun(toRun({ run_id: 2, name: null, kind: null, status: null, setting_version_display: null }));
  assert.equal(row.id, '2');
  assert.equal(row.name, '회차 2');
  assert.equal(row.kindLabel, '연간');
  assert.equal(row.status, RUN_STATUS.UNKNOWN);
  assert.equal(row.version, '-');
  assert.equal(row.created, '-');
  assert.equal(row.review, '-');
  assert.equal(row.period, '-');
});

test('어드민 회차 한 줄: 반기 참고와 검토 시작일', () => {
  const row = toAdminRun(toRun({ run_id: 3, name: '2027 상반기 참고', kind: '반기 참고', status: '참고', opened_at: '2027-03-02T09:00:00' }));
  assert.equal(row.kindLabel, '반기 참고');
  assert.equal(row.status, '참고');
  assert.equal(row.review, '2027.03.02');
});

test('서버가 근거 지점을 주지 않으면 0곳이 아니라 null이다', () => {
  const list = toCandidateList({ run: run2, candidates: [cand('a', '수정구', 50, 1)] }, { role: 'city' }, { gu: null, guList: GUS, allGu: ALL });
  const row = [...list.items, ...list.unrated][0];
  assert.equal(row.points, null);
  assert.equal(row.complaintPoints, null);
});

test('상세의 민원은 서버 건수를 쓰고, 위치가 정확하지 않은 건수는 두 건수의 차이다', () => {
  const list = toCandidateList({ run: run2, candidates: [cand('a', '수정구', 50, 1)] }, { role: 'city' }, { gu: null, guList: GUS, allGu: ALL });
  const d = toCandidateDetail({ ...cand('a', '수정구', 50, 1), complaint_cnt: 12, complaint_cnt_excl_low: 9 }, { list, user: { role: 'city' }, record: null });
  assert.equal(d.complaint.has, true);
  assert.equal(d.complaint.total, 12); // 위치가 정확하지 않은 민원도 건수에 넣는다
  assert.equal(d.complaint.lowAccuracy, 3);
  assert.deepEqual(d.complaint.types, []);
  const none = toCandidateDetail({ ...cand('a', '수정구', 50, 1), complaint_cnt: null, complaint_cnt_excl_low: null }, { list, user: { role: 'city' }, record: null });
  assert.equal(none.complaint.has, false);
  assert.equal(none.complaint.lowAccuracy, 0);
});

test('서버 값이 없는 필터는 막을 목록으로 알린다', () => {
  const list = toCandidateList({ run: run2, candidates: [cand('a', '수정구', 50, 1)] }, { role: 'city' }, { gu: null, guList: GUS, allGu: ALL });
  assert.deepEqual(list.unavailableFilters, ['zone', 'complaint']);
});

test('후보 응답의 주소·대표 지점은 표기 규칙을 거쳐 보인다(D-59)', () => {
  const cand1 = { ...cand('a', '수정구', 50, 1), address: '성남시 수정구 신흥동 1', landmark: '해님 어린이집', address_source: '어린이집·유치원', landmark_source: '어린이집·유치원' };
  const list = toCandidateList({ run: run2, candidates: [cand1] }, { role: 'city' }, { gu: null, guList: GUS, allGu: ALL });
  const row = [...list.items, ...list.unrated][0];
  assert.equal(row.address, '성남시 수정구 신흥동 1');
  assert.equal(row.landmark, '어린이집 인근');
  const d = toCandidateDetail(cand1, { list, user: { role: 'city' }, record: null });
  assert.equal(d.landmark, '어린이집 인근');
});

test('담당 부서가 null이면 서버가 준 이유(department_reason)를 보인다', () => {
  const list = toCandidateList({ run: run2, candidates: [cand('a', '수정구', 50, 1)] }, { role: 'city' }, { gu: null, guList: GUS, allGu: ALL });
  const d = toCandidateDetail({ ...cand('a', '수정구', 50, 1), department: null, department_status: '확인 필요', department_reason: '문제 유형 연결이 없습니다.' }, { list, user: { role: 'city' }, record: null });
  assert.equal(d.dept, null);
  assert.equal(d.deptReason, '문제 유형 연결이 없습니다.');
});

test('서버 상태가 검토 중이어도 3개 구가 모두 확정했다는 값이 있으면 확정으로 본다', () => {
  assert.equal(toRun({ run_id: 2, status: '검토 중' }, { finalized: true }).status, RUN_STATUS.FINAL);
  assert.equal(toRun({ run_id: 2, status: '검토 중' }, { finalized: false }).status, RUN_STATUS.REVIEW);
  assert.equal(toRun({ run_id: 2, status: '참고' }, { finalized: true }).status, '참고'); // 참고 회차는 확정하지 않는다
});

test('구가 비어 있는 후보 수: 시 도로과에는 세어 주고 구 결정 목록에서는 뺀다', () => {
  const noGu = { ...cand('x', null, 40, 9), gu: null };
  const list = toCandidateList({ run: run2, candidates: [cand('a', '수정구', 50, 1), noGu] }, { role: 'city' }, { gu: null, guList: GUS, allGu: ALL });
  assert.equal(list.noGuCount, 1);
  assert.equal(list.items.length, 1); // 구 없는 후보는 목록·집계에 넣지 않는다
  assert.equal(list.counts.total, 1);
});

test('구 도로관리팀 응답에는 구 없는 후보가 없어 0이다', () => {
  const list = toCandidateList({ run: run2, candidates: [cand('a', '수정구', 50, 1)] }, { role: 'district', gu: '수정구' }, { gu: null, guList: GUS, allGu: ALL });
  assert.equal(list.noGuCount, 0);
});

test('회차: 후보가 0건인 공회차는 구·시 선택지에서 빼고, 어드민 목록에서는 산정 결과 없음으로 구분한다', async () => {
  const body = { runs: [{ run_id: 2, candidate_cnt: 2406 }, { run_id: 3, candidate_cnt: 0 }, { run_id: 4, candidate_cnt: 2406 }] };
  const api = apiWith(async () => response(body));
  const user = await api.listRuns();
  assert.deepEqual(user.map((r) => r.id), ['2', '4']);
  const admin = (await api.listRuns({ includeEmpty: true })).map(toAdminRun);
  assert.deepEqual(admin.map((r) => [r.id, r.noResult]), [['2', false], ['3', true], ['4', false]]);
});

test('회차: 서버가 후보 수를 주지 않으면 회차를 빼지 않는다', async () => {
  const api = apiWith(async () => response({ runs: [{ run_id: 4 }] }));
  assert.deepEqual((await api.listRuns()).map((r) => r.id), ['4']);
});
