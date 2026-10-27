// 서버 연결 모드에서 열리는 어드민 화면. 연결하지 않은 화면은 가짜 데이터를 보이지 않으려고 열지 않는다.
import { opsBackendEnabled, settingsBackendEnabled } from '../api/backend.js';

const OPEN = [
  settingsBackendEnabled && /^\/admin\/standards\/criteria(?:\/[^/]+)?\/?$/,
  opsBackendEnabled && /^\/admin\/settings\/(?:accounts|access|alerts)\/?$/,
  opsBackendEnabled && /^\/admin\/?$/, // 대시보드 (AD-01)
  opsBackendEnabled && /^\/admin\/runs\/log\/?$/, // 실행 기록 (AD-07)
].filter(Boolean);

/** 주소(쿼리·해시는 무시)가 서버 연결 모드에서 열리는 화면인지 */
export function isOpenInServerMode(to) {
  const path = String(to || '').split(/[?#]/)[0];
  return OPEN.some((re) => re.test(path));
}
