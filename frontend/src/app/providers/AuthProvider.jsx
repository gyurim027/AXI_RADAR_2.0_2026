import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { getCurrentUser, login, logout } from '../../api/session.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => getCurrentUser());

  const signIn = useCallback(async (loginId, password) => {
    const result = await login({ loginId, password });
    if (result.ok) setUser(result.user);
    return result;
  }, []);

  const signOut = useCallback(async () => {
    await logout();
    setUser(null);
  }, []);

  const value = useMemo(() => ({ user, signIn, signOut }), [user, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('AuthProvider 안에서만 쓸 수 있습니다.');
  return ctx;
}
