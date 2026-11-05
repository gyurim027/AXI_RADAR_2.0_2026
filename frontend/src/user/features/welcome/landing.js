import { backendAuthEnabled, backendHome } from '../../../api/backend.js';
import { ROLE } from '../../../shared/constants.js';

/** 로그인 직후 가장 먼저 여는 소개 화면 주소 */
export const WELCOME_PATH = '/welcome';

/** 역할별 업무 첫 화면. 서버 연결 모드는 backendHome을 따르고, 연습용 모드는 운영자만 어드민으로 간다. */
export function homePath(role) {
  if (backendAuthEnabled) return backendHome(role);
  return role === ROLE.OPERATOR ? '/admin' : '/candidates';
}

/** 소개 화면의 시작 버튼이 여는 주소. 로그인 전에 가려던 주소가 있으면 그곳으로 간다. */
export function startPath(role, next) {
  const target = typeof next === 'string' ? next : '';
  const allowed = target.startsWith('/') && !target.startsWith('//') && target !== '/login' && !target.startsWith(WELCOME_PATH);
  if (allowed && (role === ROLE.OPERATOR) === target.startsWith('/admin')) return target;
  return homePath(role);
}
