import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../../../app/providers/AuthProvider.jsx';
import { ROLE } from '../../../../shared/constants.js';
import { ACCOUNTS, MOCK_PASSWORD } from '../../../../mocks/accounts.js';
import Button from '../../../components/Button.jsx';
import { TextField } from '../../../components/FormControls.jsx';
import { LOGIN_COPY as C } from '../copy.js';
import styles from './LoginPage.module.css';

/** CM-01 로그인. 로그인하면 계정의 역할과 소속 구로 첫 화면을 연다 (U-04). */
export default function LoginPage() {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [loginId, setLoginId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={user.role === ROLE.OPERATOR ? '/admin' : '/candidates'} replace />;

  const canSubmit = loginId.trim() !== '' && password !== '';

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit || busy) return;
    setBusy(true);
    setError('');
    try {
      const r = await signIn(loginId.trim(), password);
      if (r.ok) {
        const from = location.state?.from;
        navigate(r.user.role === ROLE.OPERATOR ? '/admin' : from && from !== '/login' ? from : '/candidates', { replace: true });
      } else if (r.reason === 'locked') {
        setError(C.locked(r.lockMinutes));
      } else {
        setError(C.wrong(r.remaining, r.lockMinutes));
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={styles.page}>
      <form className={styles.card} onSubmit={onSubmit} noValidate>
        <h1 className={styles.title}>{C.title}</h1>
        <p className={styles.subtitle}>{C.subtitle}</p>

        <div className={styles.fields}>
          <TextField label={C.idLabel} value={loginId} onChange={setLoginId} autoComplete="username" name="loginId" />
          <TextField label={C.pwLabel} value={password} onChange={setPassword} type="password" autoComplete="current-password" name="password" />
        </div>

        {error ? (
          <p className={styles.error} role="alert">
            {error}
          </p>
        ) : null}

        <Button type="submit" disabled={!canSubmit} loading={busy} className={styles.submit}>
          {C.submit}
        </Button>

        <p className={styles.help}>{C.help}</p>
      </form>

      {import.meta.env.DEV ? (
        <details className={styles.dev}>
          <summary>개발용 가짜 계정 (화면 기능이 아님)</summary>
          <p>비밀번호는 모두 {MOCK_PASSWORD}</p>
          <ul>
            {ACCOUNTS.map((a) => (
              <li key={a.id}>
                <code>{a.id}</code> — {a.org}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
