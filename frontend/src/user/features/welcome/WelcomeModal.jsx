import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../../app/providers/AuthProvider.jsx';
import { InfoHelp } from '../../components/FormControls.jsx';
import { WELCOME as C } from './copy.js';
import { Burst, Star, StepArt } from './illustrations.jsx';
import { setWelcomeOpen } from '../../../shared/guide/guideStore.js';
import { clampStep, welcomeMode } from './welcomeLogic.js';
import styles from './WelcomeModal.module.css';

const FOCUSABLE = 'a[href],button:not([disabled]),[tabindex]:not([tabindex="-1"])';
const TONES = ['blue', 'mint', 'peach', 'lilac', 'green', 'amber', 'sky'];

/** 로그인 직후(또는 메뉴의 `소개`)에 뒤 화면을 흐리게 하고 위에 뜨는 소개 모달. 한 곳에서만 그린다. */
const TAB_KEY = 'radar.welcome.tab.v1';
const readTabSeen = () => {
  try { return window.sessionStorage.getItem(TAB_KEY) === '1'; } catch { return false; }
};
const writeTabSeen = () => {
  try { window.sessionStorage.setItem(TAB_KEY, '1'); } catch { /* 저장을 막은 환경에서는 이 화면을 다시 열 때 한 번 더 보인다 */ }
};

export default function WelcomeModal() {
  const { user, checking } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [seenThisTab, setSeenThisTab] = useState(readTabSeen);
  const mode = checking ? null : welcomeMode({ state: location.state, user, pathname: location.pathname, seenThisTab });
  if (!mode) return null;
  const close = () => {
    if (mode === 'replay') {
      navigate(`${location.pathname}${location.search}${location.hash}`, { replace: true, state: null });
    } else {
      writeTabSeen();
      setSeenThisTab(true);
    }
  };
  return <WelcomeDialog key={mode === 'replay' ? location.key : 'prelogin'} role={user?.role ?? 'district'} onClose={close} />;
}

function WelcomeDialog({ role, onClose }) {
  const [index, setIndex] = useState(0);
  const [tab, setTab] = useState(role);
  const [dir, setDir] = useState('next');
  const cardRef = useRef(null);
  const count = C.steps.length;
  const step = C.steps[index];
  const last = index === count - 1;

  const go = useCallback((to) => {
    setIndex((cur) => {
      const nextIndex = clampStep(to, count);
      setDir(nextIndex >= cur ? 'next' : 'prev');
      return nextIndex;
    });
  }, [count]);

  // 소개 모달이 떠 있는 동안에는 화면 안내(코치마크)를 시작하지 않는다
  useEffect(() => {
    setWelcomeOpen(true);
    return () => setWelcomeOpen(false);
  }, []);

  useEffect(() => {
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    cardRef.current?.focus();
    const onKey = (e) => {
      if (e.key === 'Escape') { e.stopPropagation(); onClose(); return; }
      if (e.key === 'ArrowRight') { go(index + 1); return; }
      if (e.key === 'ArrowLeft') { go(index - 1); return; }
      if (e.key === 'Tab' && cardRef.current) {
        const items = [...cardRef.current.querySelectorAll(FOCUSABLE)];
        if (!items.length) return;
        const firstEl = items[0];
        const lastEl = items[items.length - 1];
        if (e.shiftKey && (document.activeElement === firstEl || document.activeElement === cardRef.current)) { e.preventDefault(); lastEl.focus(); }
        else if (!e.shiftKey && document.activeElement === lastEl) { e.preventDefault(); firstEl.focus(); }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
      previous?.focus?.();
    };
  }, [index, go, onClose]);

  return createPortal(
    <div className={styles.scrim} onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={styles.stage}>
        <Star className={`${styles.deco} ${styles.decoStar}`} />
        <Burst className={`${styles.deco} ${styles.decoBurst}`} />
        <span className={`${styles.deco} ${styles.decoDot}`} aria-hidden="true" />
        <section ref={cardRef} className={styles.card} role="dialog" aria-modal="true" aria-labelledby="welcome-title" tabIndex={-1}>
          <div className={styles.top} data-tone={TONES[index % TONES.length]}>
            <span className={styles.count} aria-label={`${count}단계 중 ${index + 1}단계`}>{index + 1} / {count}</span>
            <button type="button" className={styles.close} onClick={onClose} aria-label={C.closeLabel}>
              <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path d="M3 3 L13 13 M13 3 L3 13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
            </button>
            <div className={styles.art} key={step.key}><StepArt name={step.key} /></div>
          </div>

          <div className={styles.bodyWrap}>
            <div className={styles.slide} data-dir={dir} key={step.key} aria-live="polite">
              <p className={styles.kicker}>{step.kicker}</p>
              <h2 id="welcome-title" className={styles.title}>{step.title}</h2>
              <StepBody step={step} tab={tab} setTab={setTab} />
            </div>
          </div>

          <footer className={styles.foot}>
            <div className={styles.actions}>
              {index > 0 ? <button type="button" className={styles.ghost} onClick={() => go(index - 1)}>{C.prev}</button> : null}
              <button type="button" className={styles.primary} onClick={last ? onClose : () => go(index + 1)}>{last ? C.start : C.next}</button>
            </div>
            <div className={styles.dots} role="group" aria-label={C.dialogLabel}>
              {C.steps.map((s, i) => (
                <button key={s.key} type="button" className={`${styles.dot} ${i === index ? styles.dotOn : ''}`} aria-label={`${i + 1}단계로 이동`} aria-current={i === index ? 'step' : undefined} onClick={() => go(i)} />
              ))}
            </div>
          </footer>
        </section>
      </div>
    </div>,
    document.body,
  );
}

function StepBody({ step, tab, setTab }) {
  switch (step.key) {
    case 'intro':
      return (
        <>
          <p className={styles.lead}>{step.lead}</p>
          <div className={styles.panel}><span className={styles.chip}>{step.blockLabel}</span><p className={styles.text}>{step.block}</p></div>
        </>
      );
    case 'solution':
      return (
        <>
          <p className={styles.lead}>{step.lead}</p>
          <ul className={styles.list}>{step.points.map((p) => <li key={p}>{p}</li>)}</ul>
        </>
      );
    case 'effect':
      return (
        <>
          <ul className={`${styles.list} ${styles.listTwo}`}>{step.points.map((p) => <li key={p}>{p}</li>)}</ul>
          <p className={styles.note}>{step.note}</p>
        </>
      );
    case 'guide': {
      const current = step.tabs.find((t) => t.key === tab) || step.tabs[0];
      return (
        <>
          <div className={styles.tabs} role="tablist" aria-label={step.title}>
            {step.tabs.map((t) => (
              <button key={t.key} type="button" role="tab" aria-selected={t.key === current.key} className={`${styles.tab} ${t.key === current.key ? styles.tabOn : ''}`} onClick={() => setTab(t.key)}>
                {t.label}
              </button>
            ))}
          </div>
          <ol className={styles.flow} role="tabpanel">
            {current.steps.map((f, i) => (
              <li key={f.label} className={styles.flowItem}>
                <span className={styles.num}>{i + 1}</span>
                <span className={styles.flowText}><b>{f.label}</b> {f.text}{f.help ? <span className={styles.helpSlot}><InfoHelp label={`${f.label} 도움말 보기`}>{f.help}</InfoHelp></span> : null}</span>
              </li>
            ))}
          </ol>
          <p className={styles.terms}>
            {step.terms.map((t) => (<span key={t.key} className={styles.term}>{t.label}<InfoHelp label={`${t.label} 도움말 보기`}>{t.help}</InfoHelp></span>))}
          </p>
          <p className={styles.note}>{step.note}</p>
        </>
      );
    }
    case 'done':
      return (
        <>
          <p className={styles.lead}>{step.lead}</p>
          <ul className={`${styles.list} ${styles.check}`}>{step.points.map((p) => <li key={p}>{p}</li>)}</ul>
        </>
      );
    case 'next':
      return <ul className={`${styles.list} ${styles.arrow}`}>{step.points.map((p) => <li key={p}>{p}</li>)}</ul>;
    case 'team':
      return (
        <ol className={styles.phases}>
          {step.phases.map((h) => (
            <li key={h.key} className={styles.phase}>
              <p className={styles.phaseHead}><span className={styles.chip}>{h.step}</span><span className={styles.mutedText}>{h.period}</span></p>
              <p className={styles.phaseTitle}>{h.title}</p>
              <p className={styles.mutedText}>{h.people}</p>
            </li>
          ))}
        </ol>
      );
    default:
      return null;
  }
}
