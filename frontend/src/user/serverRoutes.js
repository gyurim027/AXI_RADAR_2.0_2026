// 서버 연결 모드에서 열리는 사용자 화면. 연결하지 않은 화면은 가짜 데이터를 보이지 않으려고 열지 않는다.
import { i07BackendEnabled, priorityBackendEnabled } from '../api/backend.js';

const OPEN = [
  priorityBackendEnabled && /^\/candidates\/?$/, // 점검 후보 (US-01~03): 점수·순위 모델 결과
  priorityBackendEnabled && /^\/reports\/conditions\/?$/, // 우선순위 점수 근거 (US-07)
  priorityBackendEnabled && /^\/reports\/annual\/?$/, // 관할 부서별 점검 요청서 미리보기 (US-05, H-01)
  i07BackendEnabled && /^\/reference\/approvals\/?$/, // 승인 대기 (US-10)
].filter(Boolean);

/** 주소(쿼리·해시는 무시)가 서버 연결 모드에서 열리는 사용자 화면인지 */
export function isUserOpenInServerMode(to) {
  const path = String(to || '').split(/[?#]/)[0];
  return OPEN.some((re) => re.test(path));
}
