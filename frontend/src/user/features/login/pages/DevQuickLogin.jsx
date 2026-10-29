import { backendAuthEnabled } from '../../../../api/backend.js';
import { MOCK_PASSWORD } from '../../../../mocks/accounts.js';
import styles from './DevQuickLogin.module.css';

// 개발용 빠른 로그인. 배포 전에 이 파일과 LoginPage의 'DEV-QUICK-LOGIN' 표시 두 곳을 지운다.
// 아이디는 시험 계정과 같다(서버 시험 계정은 가짜 서버 계정과 같은 아이디로 만든다).
const ACCOUNTS = [
  { label: '수정구', id: 'suj' },
  { label: '중원구', id: 'jungwon' },
  { label: '분당구', id: 'bundang' },
  { label: '성남시 (시 도로과)', id: 'city' },
  { label: 'RADAR 운영자', id: 'operator' },
];

/**
 * 누르면 아이디와 비밀번호를 채운다. 로그인은 로그인 버튼으로 직접 누른다. 개발 화면에서만 보인다.
 * 비밀번호: 가짜 서버(연습용)는 고정값, 서버에 붙었을 때는 frontend/.env.local의 VITE_DEV_LOGIN_PASSWORD.
 * 이 값은 저장소에 올리지 않는다(.env.local은 git에 올라가지 않는다). 배포 환경에는 넣지 않는다.
 */
export default function DevQuickLogin({ onPick, disabled }) {
  if (!import.meta.env.DEV) return null;
  const password = backendAuthEnabled ? import.meta.env.VITE_DEV_LOGIN_PASSWORD || '' : MOCK_PASSWORD;
  return (
    <section className={styles.box} aria-label="개발용 빠른 로그인">
      <p className={styles.title}>개발용 빠른 로그인 (배포 때 지움)</p>
      <div className={styles.row}>
        {ACCOUNTS.map((a) => (
          <button key={a.id} type="button" className={styles.btn} disabled={disabled} onClick={() => onPick(a.id, password)}>
            {a.label}
          </button>
        ))}
      </div>
      {backendAuthEnabled && !password ? (
        <p className={styles.hint}>서버 로그인 비밀번호가 없어 아이디만 채웁니다. frontend/.env.local에 VITE_DEV_LOGIN_PASSWORD를 넣으면 비밀번호도 채워집니다.</p>
      ) : null}
    </section>
  );
}
