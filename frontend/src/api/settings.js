// 62 원문만 제공한다. 숫자 설정·적용 회차·영향·현재 활성 버전을 추측하지 않는다.
import { backendRequest } from './backend.js';

export function listStoredSettings({kind='',status='',offset=0}={}) {
  const query=new URLSearchParams({limit:'100',offset:String(offset)});
  if(kind) query.set('kind',kind);
  if(status) query.set('status',status);
  return backendRequest(`/api/settings/versions?${query}`);
}

export function getStoredSetting(id) {
  return backendRequest(`/api/settings/versions/${encodeURIComponent(id)}`);
}
