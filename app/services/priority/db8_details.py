"""DB78 eight-field codec and read adapter. No file reads/writes or DDL.
Prepared module: not installed into the application until schema/legacy checks pass.
"""
import json,math
from decimal import Decimal
FIELDS=('domain_scores','indicator_contributions','unevaluated_reasons','confidence_grade','score_excluding_accidents','exclusion_reasons','complaint_contribution','policy_version')
COLS=('domain_scores_json','indicator_contributions_json','unevaluated_reasons_json','confidence_grade','score_excluding_accidents','exclusion_reasons_json','complaint_contribution','policy_version')
JSON_INDEXES={0,1,2,5}
class DetailBlocked(ValueError):pass

def _pairs(pairs):
    d={}
    for k,v in pairs:
        if k in d:raise DetailBlocked('DUPLICATE_DB_DETAIL_JSON_KEY')
        d[k]=v
    return d

def _reject(_):raise DetailBlocked('NONFINITE_JSON_VALUE')
def _number(v,score=False):
    if isinstance(v,bool) or not isinstance(v,(int,float,Decimal,str)):raise DetailBlocked('INVALID_DETAIL_NUMBER')
    try:n=Decimal(str(v))
    except Exception:raise DetailBlocked('INVALID_DETAIL_NUMBER') from None
    if not n.is_finite() or (score and not 0<=n<=100):raise DetailBlocked('INVALID_DETAIL_NUMBER')
    return n

def _validate(data,complete):
    if set(data)!=set(FIELDS):raise DetailBlocked('EIGHT_DETAIL_FIELDS_REQUIRED')
    if complete and any(data[k] is None for k in FIELDS):raise DetailBlocked('NEW_RUN_COMPLETE_DETAILS_REQUIRED')
    for k in FIELDS[:2]:
        v=data[k]
        if v is not None:
            if not isinstance(v,dict):raise DetailBlocked('INVALID_SCORE_DETAIL_OBJECT')
            for n in v.values():
                if n is not None:_number(n,True)
    for k in ('unevaluated_reasons','exclusion_reasons'):
        if data[k] is not None and not isinstance(data[k],(dict,list)):raise DetailBlocked('INVALID_REASON_DETAIL')
    if data['confidence_grade'] is not None and (not isinstance(data['confidence_grade'],str) or not 0<len(data['confidence_grade'])<=40):raise DetailBlocked('INVALID_CONFIDENCE_GRADE')
    if data['policy_version'] is not None and (not isinstance(data['policy_version'],str) or not 0<len(data['policy_version'])<=255):raise DetailBlocked('INVALID_POLICY_VERSION')
    if data['score_excluding_accidents'] is not None:_number(data['score_excluding_accidents'],True)
    if data['complaint_contribution'] is not None:_number(data['complaint_contribution'])

def _json_default(v):
    if isinstance(v,Decimal):return str(v)
    raise TypeError(type(v).__name__)

def db8_params(data,*,complete=True):
    _validate(data,complete)
    out=[]
    for i,k in enumerate(FIELDS):
        v=data[k]
        if v is None:out.append(None)
        elif i in JSON_INDEXES:out.append(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False,default=_json_default))
        elif k in ('score_excluding_accidents','complaint_contribution'):
            n=_number(v,k=='score_excluding_accidents');q=n.quantize(Decimal('.000001'))
            if n!=q or abs(q)>Decimal('999999999999.999999'):raise DetailBlocked('DETAIL_EXCEEDS_DECIMAL_18_6')
            out.append(q)
        else:out.append(v)
    return tuple(out)

def assert_db8_columns(cur):
    cur.execute('SELECT COLUMN_NAME AS name,DATA_TYPE AS data_type,IS_NULLABLE AS nullable,COLUMN_TYPE AS column_type FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s',('priority_candidate',))
    cols={r['name']:r for r in cur.fetchall()}
    if not set(COLS)<=set(cols):raise DetailBlocked('DB78_EIGHT_DETAIL_COLUMNS_MISSING')
    for i,k in enumerate(COLS):
        expected='json' if i in JSON_INDEXES else 'decimal' if i in (4,6) else 'varchar'
        if cols[k]['data_type'].lower()!=expected or cols[k]['nullable']!='YES':raise DetailBlocked('DB78_DETAIL_COLUMN_TYPE_MISMATCH')
        full='decimal(18,6)' if i in (4,6) else 'varchar(40)' if i==3 else 'varchar(255)' if i==7 else 'json'
        if cols[k]['column_type'].lower()!=full:raise DetailBlocked('DB78_DETAIL_COLUMN_SIZE_MISMATCH')

def decode_db_row(row):
    data={}
    for i,(logical,col) in enumerate(zip(FIELDS,COLS)):
        v=row[col]
        if v is not None and i in JSON_INDEXES:
            if isinstance(v,(str,bytes,bytearray)):
                try:v=json.loads(v,object_pairs_hook=_pairs,parse_constant=_reject)
                except (ValueError,UnicodeError) as e:
                    if isinstance(e,DetailBlocked):raise
                    raise DetailBlocked('INVALID_DB_DETAIL_JSON') from None
        data[logical]=v
    _validate(data,False)
    present=[k for k in FIELDS if data[k] is not None]
    version='EIGHT' if len(present)==8 else 'LEGACY_FIVE' if set(present)==set(FIELDS[:5]) else 'PARTIAL' if present else 'UNSTORED'
    return {'stored':bool(present),'storage':'DB78','evidence_version':version,'complete':len(present)==8,'missing_fields':[k for k in FIELDS if data[k] is None],**data}

def read_db_evidence(read_only,run_id,gid):
    if type(run_id) is not int or run_id<=0 or not isinstance(gid,str) or not gid.strip():raise DetailBlocked('INVALID_CANDIDATE_IDENTITY')
    rows=read_only('SELECT '+','.join(COLS)+' FROM priority_candidate WHERE run_id=%s AND gid=%s',(run_id,gid))
    if len(rows)!=1:raise DetailBlocked('CANDIDATE_IDENTITY_NOT_FOUND')
    return decode_db_row(rows[0])
