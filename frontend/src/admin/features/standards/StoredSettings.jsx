import {useState} from 'react';
import {Link,useNavigate,useParams} from 'react-router-dom';
import {getStoredSetting,listStoredSettings} from '../../../api/settings.js';
import {useAsync} from '../../../shared/hooks/useAsync.js';
import Badge from '../../components/Badge.jsx';
import Button from '../../components/Button.jsx';
import DataTable from '../../components/DataTable.jsx';
import {SelectInput} from '../../components/Field.jsx';
import Loadable from '../../components/Loadable.jsx';
import PageHeader from '../../components/PageHeader.jsx';
import Toolbar from '../../components/Toolbar.jsx';

const tones={'제안':'warning','승인':'success','돌려보냄':'danger'};
const text=value=>value===null||value===undefined||value===''?'미기록':String(value);

export function StoredSettingsList(){
  const [kind,setKind]=useState('');const [status,setStatus]=useState('');const [offset,setOffset]=useState(0);
  const navigate=useNavigate();
  const state=useAsync(()=>listStoredSettings({kind,status,offset}),[kind,status,offset]);
  return <div>
    <PageHeader title="산정 기준" subtitle="저장된 설정과 제안·승인·돌려보냄 기록을 조회합니다. 승인 상태는 실제 계산에 사용됐다는 뜻이 아닙니다."/>
    <Toolbar actions={<Button onClick={state.reload}>새로고침</Button>}>
      <SelectInput label="설정 종류" value={kind} onChange={v=>{setKind(v);setOffset(0);}} options={[{value:'',label:'전체'},'가중치','기준값','우선 확인 조건']}/>
      <SelectInput label="처리 상태" value={status} onChange={v=>{setStatus(v);setOffset(0);}} options={[{value:'',label:'전체'},'제안','승인','돌려보냄']}/>
    </Toolbar>
    {state.failed&&<p role="alert">{state.error?.message||'설정을 조회하지 못했습니다.'}</p>}
    <Loadable state={state} areaName="산정 기준" rows={4}>{data=><>
      {data.versions.length?<DataTable caption="저장된 산정 설정" columns={[
        {key:'settingVersionId',header:'설정 번호',first:true},
        {key:'settingKind',header:'설정 종류'},
        {key:'versionLabel',header:'버전 이름',render:r=>text(r.versionLabel)},
        {key:'approvalStatus',header:'처리 상태',render:r=><Badge tone={tones[r.approvalStatus]||'neutral'}>{text(r.approvalStatus)}</Badge>},
        {key:'proposedAt',header:'제안 시각',render:r=>text(r.proposedAt)},
        {key:'approvedAt',header:'처리 시각',render:r=>text(r.approvedAt)},
      ]} rows={data.versions} getRowKey={r=>r.settingVersionId} onRowClick={r=>navigate(`/admin/standards/criteria/${r.settingVersionId}`)} rowLabel={r=>`설정 ${r.settingVersionId} ${text(r.versionLabel)} 상세 보기`}/>:<p>조건에 맞는 저장된 설정이 없습니다.</p>}
      <div style={{display:'flex',gap:12,marginTop:16}}><Button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-100))}>이전</Button><Button disabled={!data.hasMore} onClick={()=>setOffset(offset+100)}>다음</Button></div>
    </>}</Loadable>
    <p style={{marginTop:24}}>설정 내용 편집·제안 생성·계산 미리보기는 아직 연결되지 않았습니다.</p>
  </div>;
}

export function StoredSettingDetail(){
  const {version}=useParams();const state=useAsync(()=>getStoredSetting(version),[version]);
  return <div>
    <Link to="/admin/standards/criteria">산정 기준 목록</Link>
    <PageHeader title="산정 기준 상세" subtitle="설정 번호로 식별한 저장 원문과 처리 기록입니다. 활성 설정을 자동 선택하지 않습니다."/>
    <Button onClick={state.reload}>새로고침</Button>
    {state.failed&&<p role="alert">{state.error?.message||'설정을 조회하지 못했습니다.'}</p>}
    <Loadable state={state} areaName="산정 기준 상세" rows={4}>{r=><>
      <DataTable caption="설정과 승인 기록" columns={[{key:'name',header:'항목',first:true},{key:'value',header:'저장값'}]} rows={[
        ['설정 번호',r.settingVersionId],['설정 종류',r.settingKind],['버전 이름',r.versionLabel],['처리 상태',r.approvalStatus],
        ['제안자 번호',r.proposedBy],['제안 시각',r.proposedAt],['처리자 번호',r.approvedBy],['처리 시각',r.approvedAt],['검토 의견',r.reviewComment],
      ].map(([name,value])=>({name,value:text(value)}))} getRowKey={v=>v.name}/>
      <h2 style={{marginTop:24}}>설정 내용 또는 파일 위치</h2>
      <pre style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere',fontFamily:'inherit'}}>{text(r.contentRef)}</pre>
      <p>승인·돌려보냄은 시 도로과의 승인 대기 화면에서 같은 설정 번호를 대상으로 처리합니다. 여기서는 값을 변경하지 않습니다.</p>
    </>}</Loadable>
  </div>;
}
