"""A-02 standard data API collector. Explicit CLI use only; no scheduler or DB writes."""
import argparse
import json
import os
import time
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

ENDPOINTS={
 'DAT-06':('tn_pubr_public_pedestrian_road_api',{'signguNm','ctprvnNm'}),
 'DAT-07':('tn_pubr_public_crosswalk_api',{'signguNm','ctprvnNm'}),
 'DAT-08':('tn_pubr_public_child_prtc_zn_api',{'institutionNm'}),
 'DAT-09':('tn_pubr_public_oldnddspsnprt_carea_api',{'signguNm','ctprvnNm'}),
 'DAT-12':('tn_pubr_public_scrty_lmp_api',{'INSTITUTION_NM'}),
}

def network(url):
    try:
        with urllib.request.urlopen(url,timeout=30) as response:
            raw=response.read(20*1024*1024+1)
            if len(raw)>20*1024*1024: raise ValueError('response_too_large')
            return raw
    except urllib.error.HTTPError as error:
        if error.code==429 or error.code>=500: raise TimeoutError('temporary_http_error') from None
        raise ValueError('http_access_failed') from None
    except (urllib.error.URLError,TimeoutError):
        raise TimeoutError('temporary_network_error') from None

def parse(raw,page,size):
    try:
        data=json.loads(raw.decode('utf-8-sig'))
        response=data.get('response', data)
        if str(response['header']['resultCode']) not in ('00','0'): raise ValueError()
        body=response['body'];total=int(body['totalCount'])
        if total<0 or int(body['pageNo'])!=page or int(body['numOfRows'])!=size: raise ValueError()
        items=body.get('items')
        if items in (None,''): items=[]
        elif isinstance(items,dict):
            items=items.get('item',[])
            if isinstance(items,dict):items=[items]
        if not isinstance(items,list) or len(items)>size or not all(isinstance(x,dict) for x in items):raise ValueError()
        return total,items
    except (KeyError,TypeError,ValueError,UnicodeError):
        raise ValueError('invalid_api_response') from None

def collect(data_id,filters,key,output_root,fetch=network,pause=time.sleep,max_pages=100):
    if data_id not in ENDPOINTS: raise ValueError('unsupported_dataset')
    endpoint,allowed=ENDPOINTS[data_id]
    if not key or not isinstance(key,str):raise ValueError('api_key_required')
    if not filters or set(filters)-allowed or not all(isinstance(v,str) and v for v in filters.values()):raise ValueError('invalid_filters')
    if not any('성남' in v for v in filters.values()):raise ValueError('explicit_seongnam_filter_required')
    if type(max_pages) is not int or not 1<=max_pages<=1000:raise ValueError('invalid_page_limit')
    folder=Path(output_root)/('api_'+uuid4().hex[:10]);folder.mkdir(parents=True,exist_ok=False)
    endpoint='https://api.data.go.kr/openapi/'+endpoint
    report=dict(data_id=data_id,endpoint=endpoint,filters=filters,received_at=datetime.now(timezone.utc).isoformat(),
        original_status='API 응답 원문',complete=False,received_rows=0,total_count=None,pages=[],
        operator_review_required=True,notification_sent=False,db_written=False,
        scope='요청 필터 범위만 수집. 성남시 전체·최신판·중복 없는 전체 시설 수를 보장하지 않습니다.')
    seen=set();size=100
    try:
        for page in range(1,max_pages+1):
            query=dict(filters,serviceKey=urllib.parse.unquote(key),type='json',pageNo=page,numOfRows=size)
            url=endpoint+'?'+urllib.parse.urlencode(query)
            raw=None
            for attempt in range(3):
                try:raw=fetch(url);break
                except TimeoutError:
                    if attempt==2:raise ValueError('retry_exhausted') from None
                    pause(attempt+1)
            total,items=parse(raw,page,size)
            if report['total_count'] is None:report['total_count']=total
            elif total!=report['total_count']:raise ValueError('total_changed_during_collection')
            expected=min(size,max(0,total-(page-1)*size))
            if len(items)!=expected:raise ValueError('page_count_mismatch')
            signatures=[json.dumps(x,sort_keys=True,ensure_ascii=False) for x in items]
            if len(set(signatures))!=len(signatures) or seen.intersection(signatures):raise ValueError('duplicate_items_review')
            seen.update(signatures)
            name=f'page_{page:04d}.json';(folder/name).write_bytes(raw)
            report['pages'].append(name);report['received_rows']+=len(items)
            if report['received_rows']==total:
                report['complete']=True
                report['operator_review_required']=(total==0)
                break
        if not report['complete']:raise ValueError('page_limit_reached')
    except ValueError as error:
        # Controlled error codes only. Never store URLs containing serviceKey or exception bodies.
        safe={'retry_exhausted','total_changed_during_collection','page_count_mismatch','duplicate_items_review','page_limit_reached','invalid_api_response','response_too_large','http_access_failed'}
        report['error_code']=str(error) if str(error) in safe else 'collection_failed'
    (folder/'collection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return folder,report

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('data_id',choices=ENDPOINTS)
    parser.add_argument('--filter',action='append',required=True,help='예: signguNm=성남시 수정구. 제공기관 표기와 정확히 일치해야 함')
    args=parser.parse_args()
    try:
        filters=dict(x.split('=',1) for x in args.filter)
        folder,report=collect(args.data_id,filters,os.environ.get('RADAR_DATA_GO_KR_KEY'),Path(__file__).resolve().parent/'outputs')
        print('수집 완료:',report['complete'],'/ 받은 행:',report['received_rows'],'/ 운영자 확인:',report['operator_review_required'])
        print('기록:',folder/'collection.json')
    except ValueError:
        print('실행 전 확인: API 키 환경변수와 자료별 성남 지역 필터를 확인하세요. 키는 채팅에 보내지 마세요.')
        raise SystemExit(2)

