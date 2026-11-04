import { useState } from 'react';
import { previewF01Caller, previewF01Verified } from '../../../api/admin.js';
import Panel from '../../components/Panel.jsx';
import Button from '../../components/Button.jsx';
import styles from './Standards.module.css';

/** F-01 → F-03 → F-04 read-only display. Never treats displayed candidates as assigned. */
export default function F01PreviewPanel() {
  const [mode, setMode] = useState('verified');
  const [gid, setGid] = useState('');
  const [sourceTable, setSourceTable] = useState('');
  const [sourceId, setSourceId] = useState('');
  const [sourceJson, setSourceJson] = useState('[]');
  const [gu, setGu] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setResult(null);
    setError('');
    if (!gid.trim() || !sourceTable.trim()) {
      setError('격자 ID와 원천 테이블이 필요합니다.'); return;
    }
    let body = { gid: gid.trim(), sourceTable: sourceTable.trim() };
    if (mode === 'verified') {
      if (!sourceId.trim()) { setError('검증 원천 ID가 필요합니다.'); return; }
      body.sourceId = sourceId.trim();
    } else {
      try {
        const rows = JSON.parse(sourceJson);
        if (!Array.isArray(rows) || rows.length < 1 || rows.length > 200 || rows.some((v) => !v || Array.isArray(v) || typeof v !== 'object')) {
          throw new Error('원천자료는 1~200개의 객체로 이루어진 JSON 배열이어야 합니다.');
        }
        body = { ...body, sourceRows: rows, gu: gu.trim() || null };
      } catch (e) { setError(`원천 JSON 오류: ${e.message}`); return; }
    }
    setBusy(true);
    try {
      setResult(await (mode === 'verified' ? previewF01Verified(body) : previewF01Caller(body)));
    } catch (e) {
      setError(`API 조회 실패: ${e.message || '서버 연결 상태를 확인해 주세요.'}`);
    } finally { setBusy(false); }
  };
  return (
    <Panel title="F-01 관할 후보 · F-03 근거등급 · F-04 공개 업무 연락처">
      <p className={styles.note}>읽기 전용 미리보기입니다. 표시된 부서는 최종 배정이 아니며 공개 팀장 직위 연락처는 대표번호가 아닙니다.</p>
      <form onSubmit={submit} className={styles.f01Form}>
        <label>조회 방식
          <select value={mode} onChange={(e) => { setMode(e.target.value); setResult(null); }}>
            <option value="verified">DB 원천 검증 조회</option>
            <option value="caller">입력자료 미검증 미리보기</option>
          </select>
        </label>
        <label>격자 ID <input value={gid} onChange={(e) => setGid(e.target.value)} required maxLength={100} /></label>
        <label>원천 테이블 <input value={sourceTable} onChange={(e) => setSourceTable(e.target.value)} required maxLength={80} /></label>
        {mode === 'verified' ? (
          <label>원천 ID <input value={sourceId} onChange={(e) => setSourceId(e.target.value)} required maxLength={120}/></label>
        ) : (
          <>
            <label>구명 (입력값이므로 검증되지 않음) <input value={gu} onChange={(e) => setGu(e.target.value)} maxLength={100}/></label>
            <label>원천 행 JSON 배열 <textarea rows={4} value={sourceJson} onChange={(e) => setSourceJson(e.target.value)}/></label>
          </>
        )}
        <Button type="submit" variant="primary" disabled={busy}>{busy ? '조회 중...' : '미리보기 조회'}</Button>
      </form>
      {error ? <p className={styles.error} role="alert">{error}</p> : null}
      {result ? (
        <div aria-live="polite">
          <p className={styles.note}>자료 출처: {result.source_provenance} · DB 쓰기: {result.db_writes} · 최종 부서 확정: 아니요</p>
          {result.results?.length ? result.results.map((r, i) => (
            <section key={`${r.source_id}-${r.problem_kind}-${i}`} className={styles.f01Result}>
              <strong>{r.problem_kind} · {r.status}</strong>
              {r.location_verification ? <p className={styles.note}>구별 위치 확인: {r.location_verification.status} ({r.location_verification.reason}){r.location_verification.warning ? ` · ${r.location_verification.warning}` : ''}</p> : null}
              <p>관할 후보: {r.candidate_departments?.map((d) => `${d.jurisdiction_id} ${d.dept_name || ''}`).join(', ') || '없음'}</p>
              <p>근거 등급: {r.basis_grade || '미확인'} ({r.confidence_label || '확인 필요'})</p>
              <p>공개 업무 연락처: {r.dept_team && r.dept_phone ? `${r.dept_team} / ${r.dept_phone}` : '정보 없음'}</p>
              {r.contact_type ? <p className={styles.note}>{r.contact_type} (대표번호 아님)</p> : null}
              {r.contact_source_ref ? <p><a href={r.contact_source_ref} target="_blank" rel="noopener noreferrer">업무분장 원본 확인</a></p> : null}
              {r.grade_source_ref ? <p className={styles.note}>등급 원본: {r.grade_source_ref}</p> : null}
              {r.display_source_status ? <p className={styles.note}>공급상태: {r.display_source_status}</p> : null}
              {r.blocked_conditions?.length ? <p className={styles.note}>차단: {r.blocked_conditions.map((x) => x.reason).join(', ')}</p> : null}
            </section>
          )) : <p>분류된 후보가 없습니다. 미해결 원천을 확인해 주세요.</p>}
        </div>
      ) : null}
    </Panel>
  );
}
