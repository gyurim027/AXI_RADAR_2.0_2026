import {viewState} from './view_state.mjs';
// Inject authenticated same-origin transport; never replace team candidate/actions API.
export function makeEvidenceClient(fetcher, publish) {
 let generation=0;
 return {
  cancel(){generation++;publish({state:'IDLE',experimentalScore:null,rank:null,details:null});},
  async load(runId,gid){
   const mine=++generation;
   publish({state:'LOADING',experimentalScore:null,rank:null,details:null});
   if(!Number.isSafeInteger(runId)||runId<=0||typeof gid!=='string'||!gid.trim()){
    publish(viewState(200,null));return;
   }
   let state;
   try{
    const response=await fetcher(`/api/scoring-result/runs/${runId}/candidates/${encodeURIComponent(gid)}`);
    const body=response.status===200?await response.json():null;
    state=response.status===200&&(body?.runId!==runId||body?.gid!==gid)?viewState(200,null):viewState(response.status,body);
   }catch{state=viewState(503,null);}
   if(mine===generation)publish(state);
  }
 };
}
