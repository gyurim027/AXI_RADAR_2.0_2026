import { useEffect, useId, useRef, useState } from 'react';
import Icon from './Icon.jsx';
import styles from './FormControls.module.css';

/** 라벨 + 선택(select). options는 문자열 목록 또는 { value, label } */
export function SelectField({ label, labelExtra, value, onChange, options, placeholder, inline = true, disabled, id: idProp, 'aria-describedby': describedBy }) {
  const autoId = useId();
  const id = idProp || autoId;
  return (
    <div className={`${styles.field} ${inline ? styles.inline : ''}`}>
      <label htmlFor={id} className={styles.label}>
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
 * ⓘ 도움말. 마우스를 올리거나 키보드 포커스가 오면 보이고, 터치 화면에서는 누르면 보인다.
 * 터치로 열었을 때는 ×로 닫는다 (바깥을 누르거나 Esc로도 닫힌다).
 */
export function InfoHelp({ label = '도움말 보기', children, align = 'left' }) {
  const [hover, setHover] = useState(false);
  const [focus, setFocus] = useState(false);
  const [pinned, setPinned] = useState(false); // 터치로 연 상태
  const id = useId();
  const ref = useRef(null);
  const lastPointer = useRef('mouse');
  const open = hover || focus || pinned;

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setPinned(false);
        setHover(false);
      }
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

  const close = () => {
    setPinned(false);
    setHover(false);
    setFocus(false);
  };

  return (
    <span
      ref={ref}
      className={styles.help}
      onPointerEnter={(e) => e.pointerType === 'mouse' && setHover(true)}
      onPointerLeave={(e) => e.pointerType === 'mouse' && setHover(false)}
      onFocusCapture={() => setFocus(true)}
      onBlurCapture={(e) => {
        if (!ref.current?.contains(e.relatedTarget)) setFocus(false);
      }}
    >
      <button
        type="button"
        className={styles.helpBtn}
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        aria-label={label}
        title={label}
        onPointerDown={(e) => {
          lastPointer.current = e.pointerType;
        }}
        onClick={() => {
          // 마우스는 올리면 열리므로 누름으로 고정하지 않는다. 터치와 펜은 누르면 열고 닫는다.
          if (lastPointer.current !== 'mouse') setPinned((v) => !v);
        }}
      >
        <Icon name="info" size={18} />
      </button>
      {open ? (
        <span id={id} role="note" className={`${styles.helpBody} ${align === 'right' ? styles.right : ''}`}>
          {children}
          {pinned ? (
            <button type="button" className={styles.helpClose} aria-label="도움말 닫기" onClick={close}>
              <Icon name="close" size={16} />
            </button>
          ) : null}
        </span>
      ) : null}
    </span>
  );
}
