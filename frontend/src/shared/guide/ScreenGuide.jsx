import { useCallback, useEffect, useState, useSyncExternalStore } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../../app/providers/AuthProvider.jsx';
import GuideTour from './GuideTour.jsx';
import { SCREENS } from './guideConfig.js';
import { filterSteps, findScreen, hasSeen, markSeen } from './guideLogic.js';
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

const POLL_MS = 250;
const POLL_MAX = 14; // 약 3.5초 동안 대상이 나타나길 기다린다
const SETTLE_MS = 700; // 처음 대상이 보인 뒤 나머지가 그려질 시간을 조금 더 준다

/** 핵심 화면에 처음 들어오면 순서 안내를 자동으로 시작하고, 상단 `?`로 다시 보게 한다. 모든 화면 위에서 한 곳만 그린다. */
export default function ScreenGuide() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const welcomeOpen = useSyncExternalStore(subscribe, getWelcomeOpen);
  const [tour, setTour] = useState(null);
  const screen = user ? findScreen(SCREENS, pathname) : null;
  const key = screen?.key;
  const role = user?.role;

  const resolve = useCallback(
    () => (screen ? filterSteps(screen.steps, role).filter((s) => document.querySelector(s.target)) : []),
    [screen, role],
  );

  useEffect(() => {
    setAvailable(false);
    if (!key || welcomeOpen) return undefined;
    let tries = 0;
    let settle = 0;
    const timer = setInterval(() => {
      tries += 1;
      if (resolve().length) {
        clearInterval(timer);
        settle = setTimeout(() => {
          const steps = resolve();
          if (!steps.length) return;
          setAvailable(true);
          if (!hasSeen(storage(), key)) {
            markSeen(storage(), key);
            setTour({ key, steps });
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
  }, [key, role, welcomeOpen, resolve]);

  useEffect(
    () => onGuideRequest(() => {
      const steps = resolve();
      if (steps.length) setTour({ key, steps });
    }),
    [resolve, key],
  );

  return tour && tour.key === key && !welcomeOpen ? <GuideTour steps={tour.steps} onClose={() => setTour(null)} /> : null;
}
