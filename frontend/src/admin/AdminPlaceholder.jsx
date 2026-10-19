import { useNavigate } from 'react-router-dom';
import { useAuth } from '../app/providers/AuthProvider.jsx';

/** 어드민(AD-00~AD-17)은 다음 단계에서 만든다. 운영자가 로그인했을 때 가는 자리만 둔다. */
export default function AdminPlaceholder() {
  const { signOut } = useAuth();
  const navigate = useNavigate();
  return (
    <div style={{ padding: 48 }}>
      <h1>어드민 준비 중</h1>
      <p style={{ margin: '16px 0' }}>RADAR 운영자 화면은 사용자 화면 다음 단계에서 만듭니다.</p>
      <button
        type="button"
        onClick={async () => {
          await signOut();
          navigate('/login', { replace: true });
        }}
      >
        로그아웃
      </button>
    </div>
  );
}
