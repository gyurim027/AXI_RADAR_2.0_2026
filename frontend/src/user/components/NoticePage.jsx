import { useNavigate } from 'react-router-dom';
import { COMMON } from '../../shared/copy/common.js';
import Button from './Button.jsx';
import { EmptyState } from './States.jsx';

/** 접근할 수 없거나 없는 화면 안내 (ERR-14~16). 말없이 다른 화면으로 보내지 않고, 이유와 다음에 할 일을 알린다. */
export default function NoticePage({ kind = 'notFound', home = '/candidates' }) {
  const navigate = useNavigate();
  const text = kind === 'forbidden' ? COMMON.forbiddenRole : COMMON.notFound;
  return (
    <div role="alert">
      <EmptyState text={text}>
        <Button variant="soft" onClick={() => navigate(home, { replace: true })}>
          {COMMON.goHome}
        </Button>
      </EmptyState>
    </div>
  );
}
