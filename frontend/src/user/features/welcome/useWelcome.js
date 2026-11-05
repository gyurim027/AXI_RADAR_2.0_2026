import { useLocation, useNavigate } from 'react-router-dom';

/** 소개 모달을 다시 연다. 지금 보는 화면은 그대로 두고 welcome 표시만 붙여 이동한다. */
export function useWelcome() {
  const navigate = useNavigate();
  const { pathname, search, hash } = useLocation();
  return { open: () => navigate(`${pathname}${search}${hash}`, { state: { welcome: true } }) };
}
