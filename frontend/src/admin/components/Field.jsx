import { useId } from 'react';
import Icon from '../../user/components/Icon.jsx';
import styles from './Field.module.css';

function Wrap({ id, label, help, error, children, inline, required }) {
  return (
    <div className={`${styles.field} ${inline ? styles.inline : ''}`}>
      <label htmlFor={id} className={styles.label}>
        {label}
        {required ? <span className={styles.required}> (필수)</span> : null}
      </label>
      {children}
      {help ? (
        <p id={`${id}-help`} className={styles.help}>
          {help}
        </p>
      ) : null}
      {error ? (
        <p id={`${id}-err`} className={styles.error} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
const describe = (id, help, error) => [help ? `${id}-help` : null, error ? `${id}-err` : null].filter(Boolean).join(' ') || undefined;

/** 라벨 + 글자 입력. 라벨은 입력창 위, 도움말·오류는 아래 (디자인 시스템 유형 C) */
export function TextInput({ label, value, onChange, help, error, placeholder, type = 'text', required, maxLength, inline, id: idProp, disabled, width }) {
  const auto = useId();
  const id = idProp || auto;
  return (
    <Wrap id={id} label={label} help={help} error={error} inline={inline} required={required}>
      <input
        id={id}
        className={`${styles.input} ${error ? styles.invalid : ''}`}
        style={width ? { width } : undefined}
        type={type}
        value={value}
        placeholder={placeholder}
        maxLength={maxLength}
        disabled={disabled}
        aria-invalid={error ? true : undefined}
        aria-describedby={describe(id, help, error)}
        onChange={(e) => onChange(e.target.value)}
      />
    </Wrap>
  );
}

export function TextArea({ label, value, onChange, help, error, placeholder, required, rows = 3, id: idProp }) {
  const auto = useId();
  const id = idProp || auto;
  return (
    <Wrap id={id} label={label} help={help} error={error} required={required}>
      <textarea
        id={id}
        className={`${styles.input} ${styles.area} ${error ? styles.invalid : ''}`}
        rows={rows}
        value={value}
        placeholder={placeholder}
        aria-invalid={error ? true : undefined}
        aria-describedby={describe(id, help, error)}
        onChange={(e) => onChange(e.target.value)}
      />
    </Wrap>
  );
}

/** 라벨 + 선택. options는 문자열 또는 { value, label } */
export function SelectInput({ label, value, onChange, options, help, error, required, inline, placeholder, id: idProp, disabled, hideLabel }) {
  const auto = useId();
  const id = idProp || auto;
  return (
    <Wrap id={id} label={hideLabel ? <span className="sr-only">{label}</span> : label} help={help} error={error} inline={inline} required={required}>
      <div className={styles.selectWrap}>
        <select
          id={id}
          className={`${styles.input} ${styles.select} ${error ? styles.invalid : ''}`}
          value={value}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={describe(id, help, error)}
          onChange={(e) => onChange(e.target.value)}
        >
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
    </Wrap>
  );
}

/** 파일 고르기. 고른 파일 이름을 입력창처럼 보인다 */
export function FileInput({ label, fileName, onChange, help, error, required, accept }) {
  const id = useId();
  return (
    <Wrap id={id} label={label} help={help} error={error} required={required}>
      <input
        id={id}
        type="file"
        className={`${styles.input} ${styles.file} ${error ? styles.invalid : ''}`}
        accept={accept}
        aria-invalid={error ? true : undefined}
        aria-describedby={describe(id, help, error)}
        onChange={(e) => onChange(e.target.files?.[0] || null)}
      />
      {fileName ? <span className="sr-only">{fileName}</span> : null}
    </Wrap>
  );
}

/** 숫자 입력 칸 (표 안). 접근성 이름을 따로 받는다 */
export function NumberCell({ value, onChange, label, suffix, disabled, width = 96, changed = false }) {
  return (
    <span className={styles.cell}>
      <input
        className={`${styles.input} ${styles.num} ${styles.cellInput} ${changed ? styles.changed : ''}`}
        style={{ width }}
        type="number"
        inputMode="decimal"
        value={value}
        aria-label={label}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value === '' ? '' : Number(e.target.value))}
      />
      {suffix ? <span className={styles.suffix}>{suffix}</span> : null}
    </span>
  );
}
