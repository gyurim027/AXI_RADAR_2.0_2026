import { backendAuthEnabled, backendHome } from '../../../api/backend.js';
import { ROLE } from '../../../shared/constants.js';

/** 역할별 업무 첫 화면. 서버 연결 모드는 backendHome을 따르고, 연습용 모드는 운영자만 어드민으로 간다. */
export function homePath(role) {
  if (backendAuthEnabled) return backendHome(role);
  return role === ROLE.OPERATOR ? '/admin' : '/candidates';
}

/** 로그인 직후 여는 화면 주소. 로그인 전에 가려던 주소가 있으면 그곳이고, 없으면 역할별 첫 화면이다. */
export function startPath(role, next) {
  const target = typeof next === 'string' ? next : '';
  const allowed = target.startsWith('/') && !target.startsWith('//') && target !== '/login';
  if (allowed && (role === ROLE.OPERATOR) === target.startsWith('/admin')) return target;
  return homePath(role);
}
