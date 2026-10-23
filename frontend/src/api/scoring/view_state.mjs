// View-consumption contract. No DOM, network wrapper, or team UI replaced.
export function viewState(httpStatus, body) {
  const empty={officialScore:null,experimentalScore:null,rank:null,details:null};
  if(httpStatus===401)return {...empty,state:'SESSION_EXPIRED',label:'로그인이 만료됐습니다',retry:false};
  if(httpStatus===403)return {...empty,state:'FORBIDDEN',label:'담당 구의 자료만 볼 수 있습니다',retry:false};
  if(httpStatus===404)return {...empty,state:'MISSING',label:'결과 또는 근거가 없습니다',retry:true};
  if(httpStatus===409)return {...empty,state:'MISMATCH',label:'회차·설정·근거가 일치하지 않습니다',retry:false};
  if(httpStatus!==200)return {...empty,state:'ERROR',label:'결과를 불러오지 못했습니다',retry:true};
  if(!body || body.officialScore!==null || body.integrationStatus!=='VERIFIED_ISOLATED_JOIN' || body.productionReady!==false)
    return {...empty,state:'INVALID',label:'검증되지 않은 응답입니다',retry:false};
  if(body.calculationStatus==='UNSCORED' && body.experimentalScore===null && body.experimentalRank===null)
    return {...empty,state:'UNSCORED',label:'미산출',details:body.details,retry:false};
  if(body.calculationStatus==='EXPERIMENTAL' && Number.isFinite(body.experimentalScore) && body.experimentalScore>=0 && body.experimentalScore<=100 && Number.isInteger(body.experimentalRank) && body.experimentalRank>0)
    return {...empty,state:'EXPERIMENTAL',label:'실험 결과 · 공식 점수 아님',experimentalScore:body.experimentalScore,rank:body.experimentalRank,details:body.details,retry:false};
  return {...empty,state:'INVALID',label:'점수 상태가 일치하지 않습니다',retry:false};
}
