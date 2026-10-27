import { mockCall } from './client.js';
import * as server from '../mocks/server.js';
import { BackendError, backendRequest, backendAuthEnabled, readBackendSession, saveBackendSession, clearBackendSession } from './backend.js';

// 로그인 성공 여부는 서버 응답만으로 정한다. 어떤 화면이 서버에 연결됐는지는 화면이 정한다.

export const getCurrentUser = () => {
  if (backendAuthEnabled) { const session = readBackendSession(); return session?.token ? session.user : null; }
  const u = server.currentUser();
  return u ? server.publicUser(u) : null;
};
const mockLogin = mockCall('login', ({ loginId, password }) => server.login(loginId, password));
export const login = async (arg) => {
  if (!backendAuthEnabled) return mockLogin(arg);
  try {
    const result = await backendRequest('/api/auth/login', { method: 'POST', body: arg });
    if (!result.token || !result.user) throw new BackendError(502, 'invalid_response', '로그인하지 못했습니다. 잠시 뒤에 다시 시도해 주세요.');
    saveBackendSession({ token: result.token, user: result.user });
    return { ok: true, user: result.user };
  } catch (error) {
    // 서버는 잠금 시간을 lock_minutes로 준다. 화면은 lockMinutes로 읽는다.
    const lockMinutes = error.details?.lock_minutes ?? error.details?.lockMinutes;
    if (error.code === 'wrong_password') return { ok: false, reason: 'wrong', remaining: error.details?.remaining, lockMinutes };
    if (error.code === 'account_locked') return { ok: false, reason: 'locked', lockMinutes };
    throw error;
  }
};
export const logout = backendAuthEnabled ? async () => clearBackendSession() : mockCall('logout', () => server.logout());
export const validateBackendSession = async () => {
  if (!backendAuthEnabled || !readBackendSession()?.token) return null;
  const data = await backendRequest('/api/auth/me');
  saveBackendSession({ ...readBackendSession(), user: data.user });
  return data.user;
};
export const listRuns = mockCall('runs', () => server.listRuns());
export const listNotifications = mockCall('notifications', () => server.listNotifications());
export const markNotificationRead = mockCall('notifications', (arg) => server.markNotificationRead(arg));
