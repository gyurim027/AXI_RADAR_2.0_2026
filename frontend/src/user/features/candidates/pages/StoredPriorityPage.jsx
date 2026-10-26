import StoredPriorityCenterMap from './StoredPriorityCenterMap.jsx';
import { useEffect, useState } from 'react';
import { backendRequest } from '../../../../api/backend.js';
import { createPriorityClient, displayValue, assertDetailMatchesList } from '../../../../api/priority.mjs';

const client = createPriorityClient(backendRequest);
function useRequest(load, identity) {
  const [state, setState] = useState({ identity: null, data: null, error: null });
  useEffect(() => {
    const controller = new AbortController(); let active = true;
    load(controller.signal).then(data => { if (active) setState({ identity, data, error: null }); })
      .catch(error => { if (active && error.name !== 'AbortError') setState({ identity, data: null, error: error.message }); });
    return () => { active = false; controller.abort(); };
  }, [load, identity]);
  return state.identity === identity ? state : { data: null, error: null };
}
const loadRuns = signal => client.runs(signal);
export default function StoredPriorityPage() {
  const { data: runs, error } = useRequest(loadRuns, 'runs');
  const [run, setRun] = useState('');
  const [compareRun, setCompareRun] = useState('');
  return <section>
    <h1>저장된 보행안전 점검 우선순위</h1>
    <p>산정 결과 조회 전용입니다. 이 화면은 평가정책 승인 여부를 증명하지 않으며, 후보 검토·확정 및 조치를 처리하지 않습니다.</p>
    {error ? <p role="alert">{error}</p> : runs === null ? <p role="status">회차 조회 중</p> : runs.length === 0 ? <p>저장된 실행회차가 없습니다. 아직 산정 결과를 표시할 수 없습니다.</p> : <>
      <label>실행회차 <select value={run} onChange={e => setRun(e.target.value)}><option value="">회차 선택</option>{runs.map(r => <option key={r.runId} value={r.runId}>{r.runId} · {r.ruleVersion ?? '판본 미제공'}</option>)}</select></label>
      {run && <>
        <label>비교할 이전 회차 <select value={compareRun} onChange={e => setCompareRun(e.target.value)}>
          <option value="">비교하지 않음</option>
          {runs.filter(r => String(r.runId) !== run).map(r => <option key={r.runId} value={r.runId}>{r.runId} · {r.ruleVersion ?? '판본 미제공'}</option>)}
        </select></label>
        {compareRun && compareRun !== run && <RunComparison key={`${compareRun}:${run}`} fromRun={Number(compareRun)} toRun={Number(run)} />}
        <RunResults key={run} run={Number(run)} />
      </>}
    </>}
  </section>;
}

function RunOperationalContext({ run }) {
  const [load] = useState(() => async signal => {
    const [rollup, conditions] = await Promise.all([
      client.runRollup(run, signal), client.runConditions(run, signal)
    ]);
    return { rollup, conditions };
  });
  const { data, error } = useRequest(load, `context:${run}`);
  if (error) return <p role="alert">회차 요약·실행조건 조회 실패: {error}</p>;
  if (!data) return <p role="status">저장 회차의 실제 근거 조회 중</p>;
  const r = data.rollup;
  return <section aria-label="회차 운영 현황">
    <h2>회차 요약 및 실행조건</h2>
    <p>대상 {r.visible_candidates ?? '미확보'}개 · 선정 {r.selected_count ?? '미확보'}개 · 점수 존재 {r.scored_count ?? '미확보'}개 · 평균 {displayValue(r.score_mean)}</p>
    <p>반기 갱신 검증: {r.halfyear_verified === true ? '검증' : '미검증'} · 개선효과: {r.action_effectiveness ?? '측정 자료 없음'}</p>
    <details><summary>실제 저장된 실행조건 응답</summary><pre>{JSON.stringify(data.conditions, null, 2)}</pre></details>
  </section>;
}

function RunResults({ run }) {
  const [load] = useState(() => signal => client.candidates(run, signal));
  const { data, error } = useRequest(load, run);
  const [gid, setGid] = useState(null);
  const [loadConditions] = useState(() => signal => client.conditions(run, signal));
  const [loadTrust] = useState(() => signal => client.trustSummary(run, signal));
  const condition = useRequest(loadConditions, `conditions:${run}`);
  const trust = useRequest(loadTrust, `trust:${run}`);
  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p role="status">결과 조회 중</p>;
  return <>
    <p>전체 {data.length}격자 · 미산출 {data.filter(r => r.score === null).length}격자</p>
    <section aria-label="회차 실행조건과 신뢰도">
      <h2>저장 회차의 실행조건 · 신뢰도</h2>
      {condition.error ? <p role="alert">조건 조회: {condition.error}</p> : condition.data ? <>
        <p>빌드: {condition.data.build_id ?? '미기록'} · 규칙: {condition.data.rule_version ?? '미기록'}</p>
        <p>설정 판본 ID: {condition.data.setting_version_id ?? 'DB에서 미확인'} · 평가기간: {condition.data.period_start ?? '미기록'} ~ {condition.data.period_end ?? '미기록'}</p>
        <p>정책·기간 기록 상태: {condition.data.contract_status ?? '확인 불가'}</p>
      </> : <p>조건 조회 중</p>}
      {trust.error ? <p role="alert">신뢰도 조회: {trust.error}</p> : trust.data ? <p>상세근거 저장 {trust.data.stored_evidence ?? 0}/{trust.data.visible_candidates ?? 0} · 신뢰도 등급 분포: {JSON.stringify(trust.data.grades ?? {})} · 근거 누락 {trust.data.missing_evidence ?? '확인 불가'}</p> : <p>신뢰도 조회 중</p>}
    </section>
    <RunOperationalContext run={run} />
    <StoredPriorityCenterMap rows={data} selectedGid={gid} onSelect={setGid} />
    <div style={{ maxHeight: '45vh', overflow: 'auto' }}><table><thead><tr><th>격자</th><th>저장 순위</th><th>저장 점수</th><th>민원 건수</th><th>근거</th></tr></thead><tbody>{data.map(row => <tr key={row.gid}><td>{row.gid}</td><td>{row.rankNo ?? '미산출'}</td><td>{displayValue(row.score)}</td><td>{row.complaintCnt ?? '미확보'}</td><td><button onClick={() => setGid(row.gid)}>근거 보기</button></td></tr>)}</tbody></table></div>
    {gid && <Evidence key={`${run}:${gid}`} run={run} gid={gid} listRow={data.find(r => r.gid === gid)} />}
  </>;
}
function Evidence({ run, gid, listRow }) {
  const [load] = useState(() => signal => client.detail(run, gid, signal));
  const { data, error } = useRequest(load, `${run}:${gid}`);
  if (error) return <p role="alert">{error}</p>;
  if (!data) return <p role="status">상세근거 조회 중</p>;
  let verified;
  try { verified = assertDetailMatchesList(listRow, data); }
  catch (error) { return <p role="alert">{error.message}</p>; }
  const d = verified.details;
  return <section aria-label="저장된 상세근거"><h2>{gid} 상세근거</h2>
    <p>점수 {displayValue(data.score)} · 순위 {data.rankNo ?? '미산출'} · 규칙판본 {data.run?.ruleVersion ?? '미확보'}</p>
    <p>민원 건수는 민원 기여점이 아닙니다. 산식·공식 승인 상태는 저장 점수만으로 판단할 수 없습니다.</p>
    {!d?.stored ? <p>상세근거가 저장되지 않았습니다.</p> : <>
      <h3>분야별 점수</h3><pre>{JSON.stringify(d.domainScores, null, 2)}</pre>
      <h3>지표별 기여점</h3><pre>{JSON.stringify(d.indicatorContributions, null, 2)}</pre>
      <h3>미평가 사유</h3><pre>{JSON.stringify(d.unevaluatedReasons, null, 2)}</pre>
      <p>신뢰도 등급: {d.confidenceGrade ?? '미확정'} · 사고 제외 점수: {displayValue(d.scoreExcludingAccidents)}</p>
    </>}
    <h3>실제 등록된 조치(82)</h3>
    {Array.isArray(data.actions) && data.actions.length > 0 ? <ul>{data.actions.map(a => <li key={String(a.item_id)}>{a.action_text ?? '조치 내용 미기록'} · {a.dept_text ?? '부서 미기록'} · {a.created_at ?? '일시 미기록'}</li>)}</ul> : <p>연결된 실제 조치 기록이 없습니다. 점수 계산만으로 조치를 생성하지 않습니다.</p>}
    <h3>저장값 설명</h3><p>{data.explanationContext?.summary ?? '설명 미산출'}</p>
    <p>외부 AI 생성 여부: {data.explanationContext?.externalApiCalled ? '호출함' : '호출하지 않음'}</p>
  </section>;
}

function RunComparison({ fromRun, toRun }) {
  const [load] = useState(() => signal => client.comparison(fromRun, toRun, signal));
  const { data, error } = useRequest(load, `${fromRun}:${toRun}`);
  if (error) return <section aria-label="회차 비교"><p role="alert">회차 비교: {error}</p></section>;
  if (!data) return <p role="status">회차 비교 조회 중</p>;
  const rows = data.comparisons;
  const added = rows.filter(r => !r.present_in_from && r.present_in_to).length;
  const removed = rows.filter(r => r.present_in_from && !r.present_in_to).length;
  const changed = rows.filter(r => r.present_in_from && r.present_in_to && (r.from_score !== r.to_score || r.from_rank !== r.to_rank || r.from_selected !== r.to_selected)).length;
  return <section aria-label="회차 비교 및 변화 요약">
    <h2>저장 회차 비교: {fromRun} → {toRun}</h2>
    <p>전체 비교 격자 {data.total} · 신규 {added} · 제외 {removed} · 점수·순위·선정 변경 {changed}</p>
    <p>저장값 사이의 차이이며, 사업 개선 효과나 사고 감소 인과관계로 해석할 수 없습니다.</p>
    <div style={{ maxHeight: '35vh', overflow: 'auto' }}><table><thead><tr><th>격자</th><th>구분</th><th>이전 점수</th><th>현재 점수</th><th>점수 변화</th><th>순위 변화</th><th>선정 전→후</th></tr></thead>
      <tbody>{rows.map(r => <tr key={r.gid}><td>{r.gid}</td><td>{!r.present_in_from ? '신규' : !r.present_in_to ? '제외' : '유지'}</td><td>{displayValue(r.from_score)}</td><td>{displayValue(r.to_score)}</td><td>{displayValue(r.score_delta)}</td><td>{r.rank_improvement ?? '비교 불가'}</td><td>{r.from_selected ?? '-'} → {r.to_selected ?? '-'}</td></tr>)}</tbody></table></div>
  </section>;
}
