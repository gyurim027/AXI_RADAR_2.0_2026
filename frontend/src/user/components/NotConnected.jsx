import { Link } from 'react-router-dom';
import { ROLE } from '../../shared/constants.js';
import { i07BackendEnabled } from '../../api/backend.js';
import { EmptyState } from './States.jsx';

/**
 * 서버 연결 모드에서 아직 서버와 연결하지 않은 화면에 보이는 안내.
 * 가짜 데이터를 대신 보이지 않는다(2026-10-27 결정). 서버에 연결된 화면이 생기면 하나씩 이 안내가 사라진다.
 */
export default function NotConnected({ role }) {
  const city = role === ROLE.CITY && i07BackendEnabled;
  return (
    <div role="status">
      <EmptyState
        text="이 화면은 아직 서버와 연결되지 않았습니다."
        hint={city ? '지금 서버에 연결된 화면은 승인 대기입니다.' : '서버에 연결된 화면이 이 계정에는 아직 없습니다. 연결되면 여기서 볼 수 있습니다.'}
      >
        {city ? <Link to="/reference/approvals">승인 대기 열기</Link> : null}
      </EmptyState>
    </div>
  );
}
