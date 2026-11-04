"""DB77 설정 참조와 실제 계산 입력의 대조. 자동 승인·값 추정·구조 조회 없음."""
from dataclasses import dataclass, asdict
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import json
import os

KINDS = ('가중치', '기준값', '우선 확인 조건')
FIELDS = ('weight_setting_version_id', 'threshold_setting_version_id',
          'priority_condition_setting_version_id')
KEYS = ('weight', 'threshold', 'priority_condition')

class SettingLinksBlocked(ValueError):
    pass

@dataclass(frozen=True)
class SettingReference:
    setting_version_id: int
    setting_kind: str
    content_ref: str
    version_label: str
    version_no: int | None

def links_enabled():
    value = os.environ.get('RADAR_PRIORITY_SETTING_LINKS', 'legacy')
    if value not in ('legacy', 'v24'):
        raise SettingLinksBlocked('INVALID_SETTING_LINKS_MODE')
    return value == 'v24'

def validate_references(refs):
    if not isinstance(refs, tuple) or len(refs) != 3:
        raise SettingLinksBlocked('THREE_EXPLICIT_SETTING_REFERENCES_REQUIRED')
    for ref, kind in zip(refs, KINDS):
        if not isinstance(ref, SettingReference) or ref.setting_kind != kind:
            raise SettingLinksBlocked('SETTING_REFERENCE_KIND_MISMATCH')
        if type(ref.setting_version_id) is not int or not 0 < ref.setting_version_id <= 9223372036854775807:
            raise SettingLinksBlocked('INVALID_SETTING_REFERENCE_ID')
        if ref.setting_version_id == 1:
            raise SettingLinksBlocked('SIMULATED_SETTING_CANNOT_AUTHORIZE_NEW_RUN')
        if not isinstance(ref.content_ref, str) or len(ref.content_ref) != 71 or not ref.content_ref.startswith('sha256:'):
            raise SettingLinksBlocked('INVALID_SETTING_REFERENCE_HASH')
        if any(c not in '0123456789abcdef' for c in ref.content_ref[7:]):
            raise SettingLinksBlocked('INVALID_SETTING_REFERENCE_HASH')
        if not isinstance(ref.version_label, str) or not ref.version_label.strip():
            raise SettingLinksBlocked('MISSING_SETTING_VERSION_LABEL')
        if ref.version_no is not None and (type(ref.version_no) is not int or ref.version_no <= 0):
            raise SettingLinksBlocked('INVALID_SETTING_DISPLAY_NUMBER')
    if len({r.setting_version_id for r in refs}) != 3:
        raise SettingLinksBlocked('ONE_SETTING_CANNOT_REPLACE_THREE_KINDS')
    return refs

def reference_identity(refs):
    return [asdict(r) for r in validate_references(refs)]

def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SettingLinksBlocked('DUPLICATE_POLICY_JSON_KEY')
        result[key] = value
    return result

def _invalid_constant(value):
    raise SettingLinksBlocked('NONFINITE_POLICY_JSON')

def read_document(row, evidence_dir):
    ref = row.get('content_ref')
    if (not isinstance(ref,str) or len(ref)!=71 or not ref.startswith('sha256:')
        or any(c not in '0123456789abcdef' for c in ref[7:])):
        raise SettingLinksBlocked('INVALID_SETTING_REFERENCE_HASH')
    raw = (Path(evidence_dir).resolve()/'policies'/(ref[7:]+'.json')).read_bytes()
    if sha256(raw).hexdigest() != ref[7:]:
        raise SettingLinksBlocked('SETTING_DOCUMENT_HASH_MISMATCH')
    doc = json.loads(raw.decode('utf-8-sig'),object_pairs_hook=_pairs,
                     parse_float=Decimal,parse_constant=_invalid_constant)
    if not isinstance(doc,dict):
        raise SettingLinksBlocked('INVALID_SETTING_DOCUMENT')
    if doc.get('policy_authority') == 'RADAR_TEAM_INTERNAL_ONLY_NOT_SEONGNAM_CITY':
        raise SettingLinksBlocked('INTERNAL_DEMO_POLICY_CANNOT_BE_RELABELED')
    if (not isinstance(doc.get('policy'),dict)
        or doc['policy'].get('label') != row.get('version_label')):
        raise SettingLinksBlocked('SETTING_DOCUMENT_LABEL_MISMATCH')
    if str(row.get('version_label')).startswith('EXP_') or doc.get('input_status') == 'EXPLORATORY_PROXY':
        raise SettingLinksBlocked('EXPLORATORY_SETTING_NOT_ALLOWED')
    return doc

def _canonical(value):
    if isinstance(value, bool):
        return ('bool', value)
    if isinstance(value, (int,float,Decimal)):
        d = Decimal(str(value))
        if not d.is_finite():
            raise SettingLinksBlocked('NONFINITE_POLICY_VALUE')
        return ('number', d)
    if isinstance(value,dict):
        return ('dict',tuple((k,_canonical(v)) for k,v in sorted(value.items())))
    if isinstance(value,list):
        return ('list',tuple(_canonical(v) for v in value))
    if value is None or isinstance(value,str):
        return (type(value).__name__,value)
    raise SettingLinksBlocked('INVALID_POLICY_VALUE')

def project(doc, kind):
    """기존 계산 문서의 필드를 대조한다. 수치·규칙을 새로 만들지 않는다."""
    try:
        p = doc['policy']
        if kind == '가중치':
            value = {'domain_weights': p['domain_weights']}
        elif kind == '기준값':
            value = {k:p[k] for k in ('normalization','observation','missing','accident_reduce')}
            value.update({k:doc[k] for k in ('complaint_mode','complaint_strength',
                'confidence_thresholds','accident_exclusion','selection_min_score',
                'input_period_start','input_period_end')})
            if 'inside_hazard_unobserved' in doc:
                value['inside_hazard_unobserved'] = doc['inside_hazard_unobserved']
        elif kind == '우선 확인 조건':
            value = {'d05_rule':doc['d05_rule']}
            if value['d05_rule'] is None:
                raise KeyError('d05_rule')
        else:
            raise SettingLinksBlocked('UNKNOWN_SETTING_KIND')
    except (KeyError,TypeError) as exc:
        raise SettingLinksBlocked('SETTING_COMPONENT_DOCUMENT_INCOMPLETE') from exc
    return _canonical(value)

def _validated_row(row, kind):
    if row.get('setting_kind') != kind:
        raise SettingLinksBlocked('SETTING_REFERENCE_KIND_MISMATCH')
    if row.get('approval_status') not in ('승인','APPROVED') or not row.get('approved_at'):
        raise SettingLinksBlocked('SETTING_REFERENCE_NOT_APPROVED')
    return SettingReference(row.get('setting_version_id'),kind,row.get('content_ref'),
                            row.get('version_label'),row.get('version_no'))

def prepare_references(reader, ids, evidence_dir, calculation_document):
    if not links_enabled():
        raise SettingLinksBlocked('DB77_V24_ACTIVATION_REQUIRED')
    if not isinstance(ids,tuple) or len(ids)!=3 or any(type(x) is not int or x<=0 for x in ids) or len(set(ids))!=3:
        raise SettingLinksBlocked('THREE_DISTINCT_SETTING_IDS_REQUIRED')
    rows = reader('SELECT setting_version_id,setting_kind,content_ref,version_label,NULL AS version_no,'
                  'approval_status,approved_at FROM setting_version '
                  'WHERE setting_version_id IN (%s,%s,%s)',ids)
    by_id={r['setting_version_id']:r for r in rows}
    if len(rows)!=3 or set(by_id)!=set(ids):
        raise SettingLinksBlocked('SETTING_REFERENCE_NOT_FOUND')
    refs=tuple(_validated_row(by_id[i],kind) for i,kind in zip(ids,KINDS))
    validate_references(refs)
    for ref in refs:
        doc=read_document(by_id[ref.setting_version_id],evidence_dir)
        if project(doc,ref.setting_kind)!=project(calculation_document,ref.setting_kind):
            raise SettingLinksBlocked('SETTING_COMPONENT_NOT_USED_BY_CALCULATION:'+ref.setting_kind)
    return refs

def verify_locked_references(cur,refs):
    validate_references(refs)
    ids=tuple(r.setting_version_id for r in refs)
    cur.execute('SELECT setting_version_id,setting_kind,content_ref,version_label,NULL AS version_no,'
                'approval_status,approved_at FROM setting_version '
                'WHERE setting_version_id IN (%s,%s,%s) ORDER BY setting_version_id FOR UPDATE',ids)
    verify_reference_rows(refs,cur.fetchall())

def verify_reference_rows(refs,rows):
    validate_references(refs)
    ids=tuple(r.setting_version_id for r in refs)
    by_id={r['setting_version_id']:r for r in rows}
    if len(rows)!=3 or set(by_id)!=set(ids):
        raise SettingLinksBlocked('SETTING_REFERENCE_NOT_FOUND')
    for ref in refs:
        if _validated_row(by_id[ref.setting_version_id],ref.setting_kind)!=ref:
            raise SettingLinksBlocked('SETTING_REFERENCE_CHANGED_BEFORE_WRITE')

def attach_run_versions(rows, reader, enabled=None):
    """v2.4 활성화 전에는 새 컬럼 조회가 없다. 표시 순번을 ID로 대신하지 않는다."""
    if enabled is None:
        enabled=links_enabled()
    out=[dict(r) for r in rows]
    if not out:
        return out
    links={};settings={}
    if enabled:
        ids=tuple(r['run_id'] for r in out)
        marks=','.join(['%s']*len(ids))
        found=reader('SELECT run_id,'+','.join(FIELDS)+' FROM priority_run WHERE run_id IN ('+marks+')',ids)
        links={r['run_id']:r for r in found}
        setting_ids=sorted({r.get(f) for r in found for f in FIELDS if r.get(f) is not None})
        if setting_ids:
            found=reader('SELECT setting_version_id,setting_kind,version_label,NULL AS version_no,'
                         'approval_status,approved_at FROM setting_version WHERE setting_version_id IN ('+
                         ','.join(['%s']*len(setting_ids))+')',tuple(setting_ids))
            settings={r['setting_version_id']:r for r in found}
    for row in out:
        values={};parts=[]
        for field,kind,key in zip(FIELDS,KINDS,KEYS):
            sid=links.get(row['run_id'],{}).get(field)
            row[field]=sid
            setting=settings.get(sid,{})
            number=setting.get('version_no')
            # An approved, correctly typed setting reference is linked even if no
            # separate display sequence was assigned. Never synthesize v52 from ID 52.
            state=('NOT_DEPLOYED' if not enabled else 'RUN_NOT_FOUND' if row['run_id'] not in links
                   else 'UNLINKED' if sid is None else 'REFERENCE_NOT_FOUND' if not setting
                   else 'KIND_MISMATCH' if setting.get('setting_kind')!=kind
                   else 'NOT_APPROVED' if setting.get('approval_status') not in ('승인','APPROVED')
                        or not setting.get('approved_at')
                   else 'INVALID_DISPLAY_NUMBER' if number is not None
                        and (type(number) is not int or number<=0)
                   else 'LINKED')
            values[key]={'setting_version_id':sid,'version_no':number if state=='LINKED' else None,
                         'version_label':setting.get('version_label'),'status':state,
                         'display_number_assigned':bool(state=='LINKED' and number is not None)}
            parts.append(kind+' v'+str(number) if state=='LINKED' and number is not None
                         else kind+' [ID '+str(sid)+'] '+str(setting.get('version_label') or '')
                         if state=='LINKED' else kind+' 미연결')
        row['setting_versions']=values
        row['setting_version_display']=' · '.join(parts)
        row['setting_links_status']='NOT_DEPLOYED' if not enabled else ('LINKED' if all(v['status']=='LINKED' for v in values.values()) else 'INCOMPLETE')
    return out
