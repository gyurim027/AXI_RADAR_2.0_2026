import { useCallback, useEffect, useRef, useState } from 'react';
import Button from '../../../components/Button.jsx';
import styles from './BottomBar.module.css';

const IDLE_MS = 1200; // 스크롤이 멈춘 뒤 숨기기까지 (와이어프레임 4)
const INTRO_MS = 3000; // 처음 들어올 때 보였다가 숨는다 (위치를 알려 주는 보완)

/**
 * 4 결정 완료 바텀 바: 우선 점검 대상 확정 버튼과 안내 글.
 * - 스크롤을 내리면 나타나고, 멈추면 숨는다.
 * - 맨 아래에 닿았을 때, 내용이 넘치지 않을 때, 막대 안에 포커스나 마우스가 있을 때는 늘 보인다.
 * scrollRef: 이 막대가 붙은 스크롤 영역(왼쪽 열)
 */
export default function BottomBar({ scrollRef, message, buttonLabel, buttonVariant = 'primary', onButton }) {
  const barRef = useRef(null);
  const [shown, setShown] = useState(true); // 스크롤·처음 진입으로 보이는 중
  const [pinned, setPinned] = useState(true); // 맨 아래·넘치지 않음
  const [engaged, setEngaged] = useState(false); // 포커스·마우스
  const lastTop = useRef(0);
  const timer = useRef(null);

  const measure = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const noOverflow = el.scrollHeight <= el.clientHeight + 1;
    const atBottom = el.scrollTop + el.clientHeight >= el.scrollHeight - 4;
    setPinned(noOverflow || atBottom);
  }, [scrollRef]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return undefined;
    measure();
    const hideLater = (ms) => {
      clearTimeout(timer.current);
      timer.current = setTimeout(() => setShown(false), ms);
    };
    hideLater(INTRO_MS);
    const onScroll = () => {
      measure();
      if (el.scrollTop > lastTop.current) setShown(true); // 내릴 때 나타난다
      lastTop.current = el.scrollTop;
      hideLater(IDLE_MS);
    };
    el.addEventListener('scroll', onScroll, { passive: true });
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    if (el.firstElementChild) ro.observe(el.firstElementChild);
    return () => {
      el.removeEventListener('scroll', onScroll);
      ro.disconnect();
      clearTimeout(timer.current);
    };
  }, [scrollRef, measure]);

  const parts = (message || '').split(/(?<=\.)\s+/).filter(Boolean);
  const visible = shown || pinned || engaged;
  return (
    <div
      ref={barRef}
      data-guide="confirm"
      className={`${styles.bar} ${visible ? '' : styles.hidden}`}
      role="region"
      aria-label="우선 점검 대상 확정"
      onFocusCapture={() => setEngaged(true)}
      onBlurCapture={(e) => {
        if (!barRef.current?.contains(e.relatedTarget)) setEngaged(false);
      }}
      onMouseEnter={() => setEngaged(true)}
      onMouseLeave={() => setEngaged(false)}
    >
      {/* 시 도로과는 버튼만 있어 글이 비어 있다. 두 문장이면 좁은 폭에서 둘째 문장이 아래 줄로 내려간다 */}
      <p className={styles.msg}>
        {parts.map((t, i) => (
          <span key={i} className={i > 0 ? styles.rest : undefined}>
            {i > 0 ? ' ' : ''}
            {t}
          </span>
        ))}
      </p>
      {buttonLabel ? (
        <Button variant={buttonVariant} className={styles.btn} onClick={onButton}>
          {buttonLabel}
        </Button>
      ) : null}
    </div>
  );
}
