import { useEffect, useMemo, useState } from 'react';
import { backendRequest } from '../../../../api/backend.js';
import { CONDITION_KEYS, CONDITION_LABELS, conditionValue, filterLiveCandidates, matchedRoleText } from './liveConditionFilters.js';

const T = {
  title: '\ubcf4\ud589\uc548\uc804 \uc810\uac80 \uc6b0\uc120\uc21c\uc704 \u2014 \uc2e4\uc81c \uc0b0\uc815 \uacb0\uacfc',
  intro: '\uacf5\uc6a9 DB77\u00b778\uc5d0 \uc800\uc7a5\ub41c \uc2e4\uc81c \uc0b0\uc815 \uacb0\uacfc\uc785\ub2c8\ub2e4.',
  caution: '\uae30\uc874 1\ud68c\ucc28 \uc77d\uae30 \uc804\uc6a9. \uac80\ud1a0\u00b7\ud655\uc815 \uc0c1\ud0dc\uc640 \uc9c0\ub3c4 \uacbd\uacc4\ub294 \uc544\uc9c1 \uc5f0\ub3d9\ud558\uc9c0 \uc54a\uc558\uc2b5\ub2c8\ub2e4.',
  round: '\ud68c\ucc28',
  total: '\uc870\ud68c \ud6c4\ubcf4',
  selected: '\uc120\uc815 \ud6c4\ubcf4',
  scored: '\uc810\uc218 \uc874\uc7ac',
  settings: '\uc124\uc815 \ucc38\uc870 \uc0c1\ud0dc',
  search: '\uaca9\uc790 ID\u00b7\uad6c \uac80\uc0c9',
  rank: '\uc21c\uc704',
  grid: '\uaca9\uc790 ID',
  gu: '\uad6c',
  score: '\uc810\uc218',
  picked: '\uc120\uc815',
  complaints: '\ubbfc\uc6d0 \uc218',
  evidence: '\uadfc\uac70 \uc800\uc7a5',
  lat: '\uc911\uc2ec \uc704\ub3c4',
  lon: '\uc911\uc2ec \uacbd\ub3c4',
  complete: '\uc644\uc804',
  partial: '\ubd80\ubd84 \uc800\uc7a5',
  missing: '\ubbf8\uc800\uc7a5',
  unavailable: '\ubbf8\uc81c\uacf5',
  unscored: '\ubbf8\uc0b0\ucd9c',
  loading: '\uc2e4\uc81c \ud6c4\ubcf4 \uc870\ud68c \uc911...',
  failure: '\uc870\ud68c \uc2e4\ud328',
  shown: '\uac74 \ud45c\uc2dc',
  detail: '\uc2e4\uc81c DB78 \uc0b0\uc815 \uadfc\uac70',
  detailLoading: '\uadfc\uac70 \uc870\ud68c \uc911...',
  prev: '\uc774\uc804',
  next: '\ub2e4\uc74c',
  page: '\ud398\uc774\uc9c0',
  empty: '\uc870\ud68c \uacb0\uacfc\uac00 \uc5c6\uc2b5\ub2c8\ub2e4.'
};

const panel = {background:'#fff', border:'1px solid #dce3ed',
  borderRadius:9, padding:16};
const th = {padding:11, textAlign:'left', borderBottom:'1px solid #dce3ed'};
const td = {padding:10, borderBottom:'1px solid #edf0f5'};
const PAGE_SIZE = 50;

export default function LivePriorityPage({ run }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [conditionFilters, setConditionFilters] = useState({result:'',hazard:'',exposure:'',vulnerable:''});
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailError, setDetailError] = useState('');

  useEffect(() => {
    let active = true;
    setResult(null);
    setError('');
    setSelected(null);
    setDetail(null);
    setPage(1);
    setQuery('');
    setConditionFilters({result:'',hazard:'',exposure:'',vulnerable:''});
    (async () => {
      try {
        const id = encodeURIComponent(run.actualRunId ?? run.id);
        const res = await backendRequest(
          `/api/priority/runs/${id}/candidates?limit=3000&offset=0`
        );
        if (!Array.isArray(res.candidates) ||
            res.candidates.length !== res.total) {
          throw new Error(`API count mismatch: ${res.candidates?.length} / ${res.total}`);
        }
        if (active) setResult(res);
      } catch (e) {
        if (active) setError(e.message || String(e));
      }
    })();
    return () => { active = false; };
  }, [run.id, run.actualRunId]);

  const rows = result?.candidates || [];
  const selectedCount = rows.filter(r => r.selectedYn === 'Y').length;
  const scoredCount = rows.filter(r => r.score != null).length;
  const filtered = useMemo(() => filterLiveCandidates(rows, query, conditionFilters),
    [rows, query, conditionFilters]);
  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visible = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  useEffect(() => {
    if (!selected) return undefined;
    let active = true;
    setDetail(null);
    setDetailError('');
    backendRequest(
      `/api/priority/runs/${encodeURIComponent(run.actualRunId ?? run.id)}` +
      `/candidates/${encodeURIComponent(selected)}`
    ).then(r => {
      if (active) setDetail(r);
    }).catch(e => {
      if (active) setDetailError(e.message || String(e));
    });
    return () => { active = false; };
  }, [selected, run.id, run.actualRunId]);

  const columns = [
    T.rank,T.grid,T.gu,T.score,T.picked,T.complaints,
    '종합','위험','노출','취약','해당 조건',T.evidence,T.lat,T.lon
  ];

  return (
    <main style={{padding:24, background:'#f5f7fb', minHeight:'100vh',
      color:'#172033'}}>
      <h1>{T.title}</h1>
      <p>{T.intro}</p>
      <p style={{color:'#8b5900'}}>{T.caution}</p>

      {error && <p role="alert">{T.failure}: {error}</p>}
      {!result && !error && <p role="status">{T.loading}</p>}

      {result && <>
        <section style={{display:'flex', flexWrap:'wrap', gap:12, margin:'20px 0'}}>
          {[
            [T.round, run.id], [T.total, result.total],
            [T.selected, selectedCount], [T.scored, scoredCount],
            [T.settings, run.settingsStatus ?? T.unavailable]
          ].map(([label,value]) =>
            <div key={label} style={{...panel,minWidth:135}}>
              <div>{label}</div>
              <strong style={{fontSize:25}}>{value}</strong>
            </div>)}
        </section>

        <label>{T.search}{' '}
          <input value={query} onChange={e => {
            setQuery(e.target.value); setPage(1);
          }} style={{padding:10,margin:'12px',minWidth:260}}/>
        </label>
        <section aria-label="공식 점검 조건 필터" style={{display:'flex',flexWrap:'wrap',gap:12,margin:'8px 0 16px'}}>
          {CONDITION_KEYS.map(key => <label key={key}>
            {CONDITION_LABELS[key]}{' '}
            <select aria-label={`${CONDITION_LABELS[key]} 조건`} value={conditionFilters[key]}
              onChange={e => {setConditionFilters(prev => ({...prev,[key]:e.target.value}));setPage(1);}}
              style={{padding:8}}>
              <option value="">전체</option>
              <option value="Y">Y (해당)</option>
              <option value="N">N (비해당)</option>
              <option value="NULL">NULL (미평가)</option>
            </select>
          </label>)}
        </section>
        <p>{filtered.length}{T.shown}</p>

        <div style={{...panel,padding:0,overflowX:'auto'}}>
          <table style={{borderCollapse:'collapse',width:'100%',fontSize:14}}>
            <thead style={{background:'#eaf0f8'}}>
              <tr>{columns.map(k => <th key={k} style={th}>{k}</th>)}</tr>
            </thead>
            <tbody>
              {visible.map(r => {
                const values = [
                  r.rankNo ?? T.unscored, r.gid, r.gu ?? T.unavailable,
                  r.score ?? T.unscored, r.selectedYn ?? '-',
                  r.complaintCnt ?? '-',
                  ...CONDITION_KEYS.map(key => conditionValue(r.conditions?.[key])),
                  matchedRoleText(r.matchedRoles),
                  r.details?.complete ? T.complete :
                    r.details?.stored ? T.partial : T.missing,
                  r.centerLat ?? '-', r.centerLon ?? '-'
                ];
                return <tr key={r.gid} onClick={() => setSelected(r.gid)}
                  style={{cursor:'pointer',
                    background:selected===r.gid?'#e6f0ff':undefined}}>
                  {values.map((value,i) =>
                    <td key={i} style={td}>{String(value)}</td>)}
                </tr>;
              })}
            </tbody>
          </table>
          {!filtered.length && <p style={{padding:16}}>{T.empty}</p>}
        </div>

        <nav aria-label={T.page} style={{display:'flex',
          alignItems:'center',gap:12,marginTop:16}}>
          <button disabled={page<=1} onClick={() => setPage(v => v-1)}>
            {T.prev}
          </button>
          <span>{T.page} {page} / {totalPages}</span>
          <button disabled={page>=totalPages} onClick={() => setPage(v => v+1)}>
            {T.next}
          </button>
        </nav>

        {selected && <section style={{...panel,marginTop:20}}>
          <h2>{T.detail} ? {selected}</h2>
          {detailError && <p role="alert">{T.failure}: {detailError}</p>}
          {!detail && !detailError && <p>{T.detailLoading}</p>}
          {detail && <>
            <p>{T.score}: {detail.score ?? T.unscored} ? {T.rank}: {detail.rankNo ?? T.unscored}</p>
            <p>점검 조건: {CONDITION_KEYS.map(key => `${CONDITION_LABELS[key]} ${conditionValue(detail.conditions?.[key])}`).join(' / ')}</p>
            <p>해당 조건: {matchedRoleText(detail.matchedRoles)}</p>
            <p>{T.evidence}: {detail.details?.complete ? T.complete :
              detail.details?.stored ? T.partial : T.missing}</p>
            <pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>
              {JSON.stringify(detail.details ?? null,null,2)}
            </pre>
          </>}
        </section>}
      </>}
    </main>
  );
}
