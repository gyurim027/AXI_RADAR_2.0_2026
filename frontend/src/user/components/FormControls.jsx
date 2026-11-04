import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import Icon from './Icon.jsx';
import { placeBubble } from './placeBubble.js';
import styles from './FormControls.module.css';

/** 라벨 + 선택(select). options는 문자열 목록 또는 { value, label } */
export function SelectField({ label, hideLabel = false, labelExtra, value, onChange, options, placeholder, inline = true, disabled, id: idProp, 'aria-describedby': describedBy }) {
  const autoId = useId();
  const id = idProp || autoId;
  return (
    <div className={`${styles.field} ${inline ? styles.inline : ''}`}>
      <label htmlFor={id} className={hideLabel ? 'sr-only' : styles.label}>
        {label}
      </label>
      {labelExtra}
      <div className={styles.selectWrap}>
        <select id={id} className={styles.select} value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled} aria-describedby={describedBy}>
          {placeholder !== undefined ? <option value="">{placeholder}</option> : null}
          {options.map((o) => {
            const v = typeof o === 'string' ? o : o.value;
            const l = typeof o === 'string' ? o : o.label;
            return (
              <option key={v} value={v}>
                {l}
              </option>
            );
          })}
        </select>
        <Icon name="chevronDown" size={18} className={styles.caret} />
      </div>
    </div>
  );
}

export function TextField({ label, value, onChange, maxLength, placeholder, type = 'text', error, autoComplete, id: idProp, name }) {
  const autoId = useId();
  const id = idProp || autoId;
  const errId = `${id}-err`;
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {label}
      </label>
      <input
        id={id}
        name={name}
        className={`${styles.input} ${error ? styles.invalid : ''}`}
        type={type}
        value={value}
        maxLength={maxLength}
        placeholder={placeholder}
        autoComplete={autoComplete}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errId : undefined}
        onChange={(e) => onChange(e.target.value)}
      />
      {error ? (
        <p id={errId} className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/**
 * ⓘ 도움말. 마우스를 올리거나 키보드 포커스가 오면 보이고, 누르면 고정된다. 고정하면 ×나 Esc, 바깥 누르기로 닫는다.
 * 말풍선은 화면 맨 위 층(portal)에 그려 칸 안의 잘림을 피하고, 화면 가장자리에서 뒤집거나 민다.
 * text가 있으면 아이콘 옆에 글자를 붙여 여러 ⓘ가 나란히 있을 때 무엇인지 구분한다.
 */
export function InfoHelp({ label = '도움말 보기', children, text, iconless = false }) {
  const [hover, setHover] = useState(false);
  const [focus, setFocus] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [pos, setPos] = useState(null);
  const id = useId();
  const ref = useRef(null);
  const bodyRef = useRef(null);
  const leaveTimer = useRef(0);
  const open = hover || focus || pinned;

  const place = useCallback(() => {
    if (!ref.current || !bodyRef.current) return;
    const a = ref.current.getBoundingClientRect();
    const b = bodyRef.current.getBoundingClientRect();
    setPos(placeBubble({ top: a.top, bottom: a.bottom, left: a.left }, { width: b.width, height: b.height }, { width: window.innerWidth, height: window.innerHeight }));
  }, []);

  useLayoutEffect(() => {
    if (!open) return undefined;
    place(); // 그리기 전에 자리를 정하므로 이전 자리가 잠깐 보이지 않는다
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
    };
  }, [open, place]);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      if (ref.current?.contains(e.target) || bodyRef.current?.contains(e.target)) return;
      setPinned(false);
      setHover(false);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') {
        setPinned(false);
        setHover(false);
        setFocus(false);
      }
    };
    document.addEventListener('pointerdown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  useEffect(() => () => clearTimeout(leaveTimer.current), []);

  const enter = (e) => {
    if (e.pointerType !== 'mouse') return;
    clearTimeout(leaveTimer.current);
    setHover(true);
  };
  // 아이콘에서 말풍선으로 건너가는 사이에 닫히지 않게 잠깐 기다린다.
  const leave = (e) => {
    if (e.pointerType !== 'mouse') return;
    leaveTimer.current = setTimeout(() => setHover(false), 120);
  };
  const close = () => {
    setPinned(false);
    setHover(false);
    setFocus(false);
  };

  return (
    <span
      ref={ref}
      className={styles.help}
      onPointerEnter={enter}
      onPointerLeave={leave}
      onFocusCapture={() => setFocus(true)}
      onBlurCapture={(e) => {
        if (!ref.current?.contains(e.relatedTarget) && !bodyRef.current?.contains(e.relatedTarget)) setFocus(false);
      }}
    >
      <button
        type="button"
        className={`${styles.helpBtn} ${text ? styles.helpBtnText : ''} ${iconless ? styles.helpBtnPlain : ''}`}
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        aria-label={label}
        onClick={() => setPinned((v) => !v)}
      >
        {iconless ? null : <Icon name="info" size={text ? 16 : 18} />}
        {text ? <span>{text}</span> : null}
      </button>
      {open
        ? createPortal(
            <span
              id={id}
              ref={bodyRef}
              role="note"
              className={styles.helpBody}
              style={pos ? { top: pos.top, left: pos.left } : { top: 0, left: 0, visibility: 'hidden' }}
              onPointerEnter={enter}
              onPointerLeave={leave}
            >
              {children}
              {pinned ? (
                <button type="button" className={styles.helpClose} aria-label="도움말 닫기" onClick={close}>
                  <Icon name="close" size={16} />
                </button>
              ) : null}
            </span>,
            document.body,
          )
        : null}
    </span>
  );
}
