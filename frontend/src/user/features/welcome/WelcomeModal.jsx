import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../../app/providers/AuthProvider.jsx';
import { InfoHelp } from '../../components/FormControls.jsx';
import { WELCOME as C } from './copy.js';
import { Burst, Star, StepArt } from './illustrations.jsx';
import { clampStep, shouldOpenWelcome } from './welcomeLogic.js';
import styles from './WelcomeModal.module.css';

const FOCUSABLE = 'a[href],button:not([disabled]),[tabindex]:not([tabindex="-1"])';
const TONES = ['blue', 'mint', 'peach', 'lilac', 'green', 'amber', 'sky'];

/** 로그인 직후(또는 메뉴의 `소개`)에 뒤 화면을 흐리게 하고 위에 뜨는 소개 모달. 한 곳에서만 그린다. */
export default function WelcomeModal() {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  if (!shouldOpenWelcome(location.state, user)) return null;
  const close = () => navigate(`${location.pathname}${location.search}${location.hash}`, { replace: true, state: null });
  return <WelcomeDialog key={location.key} role={user.role} onClose={close} />;
}

function WelcomeDialog({ role, onClose }) {
  const [index, setIndex] = useState(0);
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
              <StepBody step={step} role={role} />
            </div>
          </div>

          <footer className={styles.foot}>
            <div className={styles.actions}>
              <button type="button" className={styles.primary} onClick={last ? onClose : () => go(index + 1)}>{last ? C.start : C.next}</button>
              {index > 0 ? <button type="button" className={styles.ghost} onClick={() => go(index - 1)}>{C.prev}</button> : null}
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

function StepBody({ step, role }) {
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
    case 'flow':
      return (
        <>
          <ol className={styles.flow}>
            {step.flow.map((f, i) => (
              <li key={f.key} className={styles.flowItem}>
                <span className={styles.num}>{i + 1}</span>
                <span>{f.label}</span>
                {f.help ? <InfoHelp label={`${f.label} 도움말 보기`}>{f.help}</InfoHelp> : null}
              </li>
            ))}
          </ol>
          <ul className={styles.roles}>
            {step.roles.map((r) => (
              <li key={r.key} className={`${styles.role} ${r.key === role ? styles.roleOn : ''}`}>
                <b>{r.label}</b><span>{r.text}</span>
              </li>
            ))}
          </ul>
          <p className={styles.terms}>
            {step.terms.map((t) => (<span key={t.key} className={styles.term}>{t.label}<InfoHelp label={`${t.label} 도움말 보기`}>{t.help}</InfoHelp></span>))}
          </p>
        </>
      );
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
