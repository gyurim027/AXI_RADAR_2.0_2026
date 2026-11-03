import { mockCall } from './client.js';
import * as server from '../mocks/server.js';
import { backendRequest, backendAuthEnabled, priorityBackendEnabled, g03BackendEnabled, g06BackendEnabled, BackendError } from './backend.js';
import { createPriorityApi } from './priority.js';
import { getCurrentUser } from './session.js';
import { ALL_GU, GU_LIST } from '../shared/constants.js';

const priority = createPriorityApi(backendRequest);
const serverMode = () => backendAuthEnabled && priorityBackendEnabled;
const mockListCandidates = mockCall('candidates', (arg) => server.listCandidates(arg));
const mockGetCandidateDetail = mockCall('candidateDetail', (arg) => server.getCandidateDetail(arg));

/** 점검 후보 목록. 서버 연결 모드에서는 점수·순위 모델 결과를 쓴다. */
export const listCandidates = (arg) =>
  serverMode() ? priority.listCandidates({ ...arg, user: getCurrentUser(), guList: GU_LIST, allGu: ALL_GU }) : mockListCandidates(arg);
export const getCandidateDetail = (arg) =>
  serverMode() ? priority.getCandidateDetail({ ...arg, user: getCurrentUser() }) : mockGetCandidateDetail(arg);

const mockSaveDecision = mockCall('saveDecision', (arg) => server.saveDecision(arg));
const REASONS = {
  '제외': ['현장 확인 결과 문제 없음', '이미 정비 계획에 있음', '다른 부서 소관', '기타'],
  '보류': ['예산·공정 사정', '추가 확인 필요', '기타'],
};

/** G-03 개발용 최초 결정: 운영 DB 저장이 아닌 서버 메모리 저장이다. */
export async function saveDecision({ runId, gid, decision, reasonKey, reasonText, memo }) {
  if (!g03BackendEnabled) {
    return mockSaveDecision({ runId, gid, decision, reasonKey, reasonText, memo });
  }
  if (!['우선 점검 대상', '제외', '보류'].includes(decision)) {
    throw new BackendError(400, 'invalid', '올바르지 않은 결정입니다.');
  }
  const allowed = REASONS[decision] || [];
  if (decision !== '우선 점검 대상' && !reasonKey) return { ok: false, code: 'reasonRequired' };
  if (reasonKey && !allowed.includes(reasonKey)) {
    throw new BackendError(400, 'invalid', '선택한 결정에 사용할 수 없는 사유입니다.');
  }
  if (reasonKey === '기타' && !String(reasonText || '').trim()) return { ok: false, code: 'otherRequired' };
  const path = `/api/g03/runs/${encodeURIComponent(runId)}/candidates/${encodeURIComponent(gid)}/decision`;
  return backendRequest(path, {
    method: 'POST',
    body: {
      decision,
      reason_code: reasonKey || null,
      reason_text: reasonKey === '기타' ? String(reasonText).trim().slice(0, 100) : null,
      memo: reasonKey === '기타' ? '' : String(memo || '').slice(0, 200),
    },
  });
}

export const setDept = mockCall('setDept', (arg) => server.setDept(arg));
const mockConfirmSummary = mockCall('confirmSummary', (arg) => server.getConfirmSummary(arg));
const mockConfirmGu = mockCall('confirmGu', (arg) => server.confirmGu(arg));

/** G-06 개발용 구별 확정 요약. 운영 DB의 확정 상태가 아니다. */
export async function getConfirmSummary({ runId }) {
  if (!g06BackendEnabled) return mockConfirmSummary({ runId });
  return backendRequest(`/api/g06/runs/${encodeURIComponent(runId)}/districts/me/confirmation`);
}

/** 기존 화면의 확인 클릭 이후에만 호출한다. 미결정 후보가 있으면 재확인 플래그가 필요하다. */
export async function confirmGu({ runId, reconfirmUndecided = false }) {
  if (!g06BackendEnabled) return mockConfirmGu({ runId });
  const result = await backendRequest(`/api/g06/runs/${encodeURIComponent(runId)}/districts/me/confirmation`, {
    method: 'POST',
    body: { explicitly_confirmed: true, reconfirm_undecided: reconfirmUndecided === true },
  });
  return { gu: result.result.gu, done: result.result.district_finalized, date: null };
}
export const getGuCompare = mockCall('guCompare', (arg) => server.getGuCompare(arg));
export const logComplaintPointView = mockCall('pointView', (arg) => server.viewComplaintPoints(arg));
