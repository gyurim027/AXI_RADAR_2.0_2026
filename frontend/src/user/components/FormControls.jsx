import { useId, useState } from 'react';
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

/** ⓘ를 누르면 펼치는 도움말 (US-00 1-1, US-03 1-1) */
export function InfoHelp({ label = '도움말 보기', children, align = 'left' }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className={styles.help}>
      <button type="button" className={styles.helpBtn} aria-expanded={open} aria-controls={id} aria-label={label} title={label} onClick={() => setOpen((v) => !v)}>
        <Icon name="info" size={18} />
      </button>
      {open ? (
        <span id={id} role="note" className={`${styles.helpBody} ${align === 'right' ? styles.right : ''}`}>
          {children}
        </span>
      ) : null}
    </span>
  );
}
