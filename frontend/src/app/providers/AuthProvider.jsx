import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { getCurrentUser, login, logout, validateBackendSession } from '../../api/session.js';

import { backendAuthEnabled, readBackendSession } from '../../api/backend.js';
import { LOGIN_COPY } from '../../user/features/login/copy.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => getCurrentUser());
  const [checking, setChecking] = useState(() => backendAuthEnabled && !!readBackendSession()?.token);
  const [sessionError, setSessionError] = useState(null);
  const [loginNotice, setLoginNotice] = useState(null); // 2-13 로그인 만료 안내
  useEffect(() => {
    if (!backendAuthEnabled) return undefined;
    let alive = true;
    const expired = () => { if (alive) { setUser(null); setSessionError(null); setLoginNotice(LOGIN_COPY.expired); } };
    window.addEventListener('radar:session-expired', expired);
    validateBackendSession().then((u) => { if (alive && u) setUser(u); })
      .catch((e) => { if (alive && e.status !== 401) setSessionError(e.message); })
      .finally(() => { if (alive) setChecking(false); });
    return () => { alive = false; window.removeEventListener('radar:session-expired', expired); };
  }, []);

  const signIn = useCallback(async (loginId, password) => {
    setLoginNotice(null);
    const result = await login({ loginId, password });
    if (result.ok) { setUser(result.user); setSessionError(null); }
    return result;
  }, []);

  const signOut = useCallback(async () => {
    await logout();
    setUser(null);
    setSessionError(null);
  }, []);

  /** 운영자가 '사용자 화면 보기'를 켜거나 끌 때 화면의 계정을 다시 읽는다 */
  const refreshUser = useCallback(() => setUser(getCurrentUser()), []);

  const value = useMemo(() => ({ user, checking, sessionError, loginNotice, signIn, signOut, refreshUser }), [user, checking, sessionError, loginNotice, signIn, signOut, refreshUser]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('AuthProvider 안에서만 쓸 수 있습니다.');
  return ctx;
}
