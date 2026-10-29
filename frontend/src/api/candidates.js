import { mockCall } from './client.js';
import * as server from '../mocks/server.js';
import { backendRequest, g03BackendEnabled, BackendError } from './backend.js';

export const listCandidates = mockCall('candidates', (arg) => server.listCandidates(arg));
export const getCandidateDetail = mockCall('candidateDetail', (arg) => server.getCandidateDetail(arg));

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
export const getConfirmSummary = mockCall('confirmSummary', (arg) => server.getConfirmSummary(arg));
export const confirmGu = mockCall('confirmGu', (arg) => server.confirmGu(arg));
export const getGuCompare = mockCall('guCompare', (arg) => server.getGuCompare(arg));
export const logComplaintPointView = mockCall('pointView', (arg) => server.viewComplaintPoints(arg));
