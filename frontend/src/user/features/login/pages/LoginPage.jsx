import AppVersion from '../../../../shared/components/AppVersion.jsx';
import { useEffect, useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../../../app/providers/AuthProvider.jsx';
import { backendAuthEnabled, backendBaseUrl } from '../../../../api/backend.js';
import { WELCOME_PATH } from '../../welcome/landing.js';
import Button from '../../../components/Button.jsx';
import { TextField } from '../../../components/FormControls.jsx';
import { LOGIN_COPY as C } from '../copy.js';
import DevQuickLogin from './DevQuickLogin.jsx'; // DEV-QUICK-LOGIN
import styles from './LoginPage.module.css';

const MAX_FAILS = 5; // POL-022 잠금 기준 (5번, 10분)

/** 오류 코드로 문구를 고른다 (2-7~2-12). 모르는 코드는 2-11. */
function errorText(e) {
  switch (e?.code) {
    case 'inactive_account':
      return C.inactive;
    case 'unknown_role':
      return C.noRole;
    case 'network_error':
      return C.network;
    case 'session_unavailable':
      return C.noStorage;
    default:
      return C.other;
  }
}

/** 개발 화면에서만: 서버 주소로 실제 요청을 보내 닿는지 확인해 보여 준다. 주소만 적혀 있는 것과 서버가 켜져 있는 것은 다르다. */
function DevServerStatus() {
  const [state, setState] = useState('checking'); // checking | up | down
  useEffect(() => {
    if (!backendAuthEnabled) return undefined;
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 4000);
    fetch(`${backendBaseUrl.replace(/\/+$/, '')}/health`, { signal: ctrl.signal })
      .then((r) => setState(r.ok ? 'up' : 'down'))
      .catch(() => setState('down'))
      .finally(() => clearTimeout(timer));
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, []);
  if (!backendAuthEnabled) return <p className={styles.mode} role="note">{C.devMock}</p>;
  const cls = state === 'up' ? styles.modeLive : state === 'down' ? styles.modeDown : '';
  return (
    <p className={`${styles.mode} ${cls}`} role="note">
      {C.devServer(state, backendBaseUrl)}
    </p>
  );
}

/** CM-01 로그인. 로그인하면 계정의 역할과 소속 구로 첫 화면을 연다 (U-04). */
export default function LoginPage() {
  const { user, checking, signIn, loginNotice } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [loginId, setLoginId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (checking) return <p role="status">로그인을 확인하고 있습니다.</p>;
  if (user) return <Navigate to={WELCOME_PATH} replace />;

  const canSubmit = loginId.trim() !== '' && password !== '';

  const login = async (id, pw) => {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const r = await signIn(id.trim(), pw);
      if (r.ok) {
        const from = location.state?.from;
        navigate(WELCOME_PATH, { replace: true, state: { next: from } });
      } else if (r.reason === 'locked') {
        setError(C.locked(MAX_FAILS, r.lockMinutes));
      } else {
        setError(C.wrong(r.remaining, r.lockMinutes));
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const onSubmit = (e) => {
    e.preventDefault();
    if (canSubmit) login(loginId, password);
  };

  // DEV-QUICK-LOGIN 시작 (배포 전에 지운다)
  // 아이디와 비밀번호만 채운다. 로그인은 로그인 버튼으로 직접 누른다.
  const quickLogin = (id, pw) => {
    setLoginId(id);
    setPassword(pw);
    setError('');
  };
  // DEV-QUICK-LOGIN 끝

  return (
    <div className={styles.page}>
      <form className={styles.card} onSubmit={onSubmit} noValidate>
        <h1 className={styles.title}>{C.title}</h1>
        <p className={styles.subtitle}>{C.subtitle}</p>
        {/* 개발 화면에서만: 서버에 붙었는지 연습용 로그인인지 보인다. 연습용인데 서버 계정으로 시도하면 틀린 비밀번호로 보여 헷갈리기 때문이다. */}
        {import.meta.env.DEV ? <DevServerStatus /> : null}

        <div className={styles.fields}>
          <TextField label={C.idLabel} value={loginId} onChange={setLoginId} autoComplete="username" name="loginId" />
          <TextField label={C.pwLabel} value={password} onChange={setPassword} type="password" autoComplete="current-password" name="password" />
        </div>

        {error || loginNotice ? (
          <p className={styles.error} role="alert">
            {error || loginNotice}
          </p>
        ) : null}

        <Button type="submit" disabled={!canSubmit} loading={busy} className={styles.submit}>
          {C.submit}
        </Button>

        <p className={styles.help}>{C.help}</p>
      </form>

      {/* DEV-QUICK-LOGIN */}
      <DevQuickLogin onPick={quickLogin} disabled={busy} />
      <AppVersion />
    </div>
  );
}
