// 날짜·기준일·변수 표기 도구 (CM-00 2, 8번)

const pad = (n) => String(n).padStart(2, '0');

/** 날짜는 'YYYY.MM.DD' (CM-00 8번) */
export function formatDate(value) {
  const d = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(d.getTime())) return '기준일 미확인';
  return `${d.getFullYear()}.${pad(d.getMonth() + 1)}.${pad(d.getDate())}`;
}

/** 근거 기준일 꼬리표: '2025년 기준 (연간)', '2022년 기준 (과거 기록)', 기준일이 없으면 '기준일 미확인' (CM-00 8번, POL-020) */
export function formatBasis(basisYear, updateType) {
  if (!basisYear) return '기준일 미확인';
  const label = updateType === '1회성' ? '과거 기록' : updateType;
  return `${basisYear}년 기준${label ? ` (${label})` : ''}`;
}

/** %변수% 를 값으로 채운다 (CM-00 2번). 값이 없으면 변수 표시를 그대로 둔다. */
export function fillVars(template, vars = {}) {
  return template.replace(/%([^%]+)%/g, (whole, key) =>
    vars[key] === undefined || vars[key] === null ? whole : String(vars[key]),
  );
}

/** 보고서 파일 이름: RADAR_[회차]_[구]_[보고서 이름] (US-05 9-1) */
export function reportFileName(runName, guLabel, reportName, ext) {
  const clean = (s) => String(s).replace(/\s+/g, '').replace(/[\\/:*?"<>|]/g, '');
  return `RADAR_${clean(runName)}_${clean(guLabel)}_${clean(reportName)}.${ext}`;
}

/** 회차 이름에서 연도 (예: '2027 연간' → '2027') */
export function runYear(runName) {
  const m = String(runName).match(/\d{4}/);
  return m ? m[0] : '';
}

/** 회차 이름 끝의 '참고'를 뗀다. 띠·알림 문구가 '%회차 이름% 참고 회차'로 쓰여 '참고'가 겹치지 않게 한다. */
export function runNameWithoutRef(runName) {
  return String(runName).replace(/\s*참고$/, '');
}

/**
 * 사용자 화면에서 회차를 부르는 이름 (UX 고도화 W-9). '회차' 대신 점검하는 해로 쓴다.
 * 연간: '2027년 점검 후보', 반기 참고: '2026년 하반기 계산 (참고용)'
 */
export function runTitle(run, withNote = true) {
  const year = runYear(run.name);
  if (run.kind === 'ref') {
    const rest = runNameWithoutRef(run.name).replace(/^\d{4}\s*/, '');
    return `${year}년 ${rest} 계산${withNote ? ' (참고용)' : ''}`.replace('  ', ' ');
  }
  return `${year}년 점검 후보`;
}

/** 점검 연도 선택 칸의 선택지. 연간은 상태를 붙인다. 예: '2027년 점검 후보 · 검토 중' */
export function runOptionLabel(run) {
  return run.kind === 'ref' ? runTitle(run) : `${runTitle(run)} · ${run.status}`;
}

/** 이 회차가 쓴 자료의 해. 자료 기준일 끝 해를 쓴다. 예: '2022.12 ~ 2026.06' → '2026' */
export function dataYear(dataRange) {
  const m = String(dataRange || '').match(/(\d{4})\.\d{2}\s*$/);
  return m ? m[1] : '';
}

/** 마지막 글자의 받침에 따라 '을' 또는 '를'을 붙인다 (예: 점검 후보 목록을, 점검 후보 지도를) */
export function withEulReul(word) {
  const last = String(word).trim().slice(-1);
  const code = last.charCodeAt(0);
  const hasBatchim = code >= 0xac00 && code <= 0xd7a3 && (code - 0xac00) % 28 !== 0;
  return `${word}${hasBatchim ? '을' : '를'}`;
}

/** 마지막 글자의 받침에 따라 '이' 또는 '가'를 붙인다 (예: 지침이, 조례가) */
export function withIga(word) {
  const last = String(word).trim().slice(-1);
  const code = last.charCodeAt(0);
  const hasBatchim = code >= 0xac00 && code <= 0xd7a3 && (code - 0xac00) % 28 !== 0;
  return `${word}${hasBatchim ? '이' : '가'}`;
}

/** '으로' 또는 '로'를 붙인다. 받침이 없거나 ㄹ 받침이면 '로' (예: 데이터 목록으로, 검사 결과로) */
export function withEuro(word) {
  const last = String(word).trim().slice(-1);
  const code = last.charCodeAt(0);
  const isHangul = code >= 0xac00 && code <= 0xd7a3;
  const jong = isHangul ? (code - 0xac00) % 28 : 0;
  return `${word}${jong === 0 || jong === 8 ? '로' : '으로'}`;
}
