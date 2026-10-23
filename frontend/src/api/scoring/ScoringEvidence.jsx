import {useEffect,useMemo,useState} from 'react';
import {makeEvidenceClient} from './client.mjs';
// Opt-in panel. Pass the team's authenticated fetch transport and current run/gid.
export default function ScoringEvidence({runId,gid,fetcher}) {
 const [state,setState]=useState({state:'IDLE'});
 const client=useMemo(()=>makeEvidenceClient(fetcher,setState),[fetcher]);
 useEffect(()=>{client.load(runId,gid);return ()=>client.cancel();},[client,runId,gid]);
 return <section aria-live="polite"><h3>산정 근거</h3><p>{state.label??state.state}</p>
 {state.state==='EXPERIMENTAL'&&<p>실험 점수 {state.experimentalScore} · 동률 반영 순위 {state.rank}</p>}
 {state.details&&<><p>원시 민원 {state.details.rawComplaintCount}건 · 민원 점수항 {state.details.complaintSignalPoints??'미산출'}</p><p>{state.details.reasons?.join(' / ')}</p></>}
 </section>;
}
