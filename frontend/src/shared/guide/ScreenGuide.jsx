import { useCallback, useEffect, useState, useSyncExternalStore } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { isOpenInServerMode } from '../../admin/serverRoutes.js';
import { backendAuthEnabled } from '../../api/backend.js';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import { isUserOpenInServerMode } from '../../user/serverRoutes.js';
import GuideTour from './GuideTour.jsx';
import { FLOWS, GUIDE_COPY, SCREENS } from './guideConfig.js';
import { closingStep, filterSteps, findScreen, flowInfo, hasSeen, markSeen } from './guideLogic.js';
import { getWelcomeOpen, onGuideRequest, setAvailable, subscribe } from './guideStore.js';

// 저장소를 막은 환경에서는 이 탭 안에서만 기억한다
const memory = {};
function storage() {
  try {
    return window.localStorage;
  } catch {
    return {
      getItem: (k) => memory[k] ?? null,
      setItem: (k, v) => { memory[k] = v; },
      removeItem: (k) => { delete memory[k]; },
    };
  }
}

// 서버 연결 모드에서 열리지 않는 화면은 경로에서 건너뛴다. 연습용 모드는 모두 열려 있다.
const isOpenPath = (path) => !backendAuthEnabled || (path.startsWith('/admin') ? isOpenInServerMode(path) : isUserOpenInServerMode(path));

const POLL_MS = 250;
const POLL_MAX = 14; // 약 3.5초 동안 대상이 나타나길 기다린다
const SETTLE_MS = 700; // 처음 대상이 보인 뒤 나머지가 그려질 시간을 조금 더 준다

/**
 * 핵심 화면에 처음 들어오면 순서 안내를 자동으로 시작하고, 계정 영역의 `?`로 다시 보게 한다. 모든 화면 위에서 한 곳만 그린다.
 * 안내의 마지막 카드가 다음 화면으로 이어 주고, 그 이동 버튼으로 온 화면은 이미 본 화면이어도 바로 시작한다.
 */
export default function ScreenGuide() {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const { pathname, search, hash } = location;
  const forced = location.state?.guideFlow === true;
  const welcomeOpen = useSyncExternalStore(subscribe, getWelcomeOpen);
  const [tour, setTour] = useState(null);
  const screen = user ? findScreen(SCREENS, pathname) : null;
  const key = screen?.key;
  const role = user?.role;

  // 화면에 실제로 있는 단계만 남기고, 핵심 경로의 마지막 카드를 붙인다. 안내할 단계가 하나도 없으면 시작하지 않는다.
  const resolve = useCallback(() => {
    if (!screen) return null;
    const steps = filterSteps(screen.steps, role).filter((s) => document.querySelector(s.target));
    if (!steps.length) return null;
    const info = flowInfo(FLOWS, SCREENS, role, screen.key, isOpenPath);
    const closing = closingStep(info, GUIDE_COPY);
    return { key: screen.key, steps: closing ? [...steps, closing] : steps };
  }, [screen, role]);

  useEffect(() => {
    setAvailable(false);
    if (!key || welcomeOpen) return undefined;
    let tries = 0;
    let settle = 0;
    const timer = setInterval(() => {
      tries += 1;
      if (resolve()) {
        clearInterval(timer);
        settle = setTimeout(() => {
          const next = resolve();
          if (!next) return;
          setAvailable(true);
          if (forced || !hasSeen(storage(), key)) {
            markSeen(storage(), key);
            setTour(next);
            if (forced) navigate(`${pathname}${search}${hash}`, { replace: true, state: null }); // 새로고침에서 다시 뜨지 않게
          }
        }, SETTLE_MS);
      } else if (tries >= POLL_MAX) {
        clearInterval(timer);
      }
    }, POLL_MS);
    return () => {
      clearInterval(timer);
      clearTimeout(settle);
      setAvailable(false);
    };
  }, [key, role, welcomeOpen, forced, resolve, navigate, pathname, search, hash]);

  useEffect(
    () => onGuideRequest(() => {
      const next = resolve();
      if (next) setTour(next);
    }),
    [resolve],
  );

  const go = (to) => {
    setTour(null);
    navigate(to, { state: { guideFlow: true } });
  };

  return tour && tour.key === key && !welcomeOpen ? <GuideTour steps={tour.steps} onClose={() => setTour(null)} onGo={go} /> : null;
}
