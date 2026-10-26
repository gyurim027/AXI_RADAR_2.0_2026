"""Atomic human relevance decision using existing RADAR tables and explicit audit evidence.
Do not classify a review as population-wide confirmation without full-coverage reconciliation.
"""
from __future__ import annotations
from app.core import db
from app.core.responses import ApiError

VALID = {'보행안전 관련','비관련'}

def record_decision(complaint_id, relevance, reason, actor_id, expected_relevance=None):
    if relevance not in VALID or len(str(reason).strip()) < 8:
        raise ApiError(422,'invalid_review','검토 결정 또는 사유가 유효하지 않습니다')
    with db.connect() as con:
        try:
            with con.cursor() as cur:
                cur.execute('SELECT complaint_id,relevance,class_method,ped_type FROM src_complaint WHERE complaint_id=%s FOR UPDATE',(complaint_id,))
                row=cur.fetchone()
                if not row: raise ApiError(404,'complaint_not_found','민원 ID가 없습니다')
                before=row.get('relevance')
                if expected_relevance is not None and before!=expected_relevance:
                    raise ApiError(409,'stale_source','조회 후 관련성 값이 바뀌었습니다')
                if row.get('class_method')=='사람':
                    raise ApiError(409,'already_human_reviewed','이미 사람 검토 기록이 있어 재검토 절차가 필요합니다')
                # These values are the reviewer's actual input, NOT auto-acceptance of AI/rules.
                # Change ledger records decision even when same as current AI suggestion.
                for col,old,new in [('relevance',before,relevance),('class_method',row.get('class_method'),'사람')]:
                    cur.execute('INSERT INTO src_complaint_change (complaint_id,changed_column,old_value,new_value,load_batch,changed_by_type,changed_by_user) VALUES (%s,%s,%s,%s,NULL,%s,%s)',
                                (complaint_id,col,old,new,'사람',actor_id))
                if relevance=='비관련' and row.get('ped_type') is not None:
                    cur.execute('INSERT INTO src_complaint_change (complaint_id,changed_column,old_value,new_value,load_batch,changed_by_type,changed_by_user) VALUES (%s,%s,%s,NULL,NULL,%s,%s)',
                                (complaint_id,'ped_type',row['ped_type'],'사람',actor_id))
                cur.execute('UPDATE src_complaint SET relevance=%s,class_method=%s,ped_type=CASE WHEN %s=%s THEN NULL ELSE ped_type END,db_last_updated_at=NOW() WHERE complaint_id=%s',
                            (relevance,'사람',relevance,'비관련',complaint_id))
                cur.execute("INSERT INTO access_audit (actor_ref,resource_kind,resource_key,client_ip,access_reason) VALUES (%s,'C08 관련성 확정',%s,NULL,%s)",
                            (actor_id,complaint_id,'HUMAN_ROW_DECISION: '+str(reason).strip()))
            con.commit()
        except Exception:
            con.rollback()
            raise
    return {'complaint_id':complaint_id,'relevance':relevance,'reviewed_by':actor_id,
            'human_decision_recorded':True,'population_confirmed':False,
            'c07_official_allowed':False,'reason':'row-level review only; population reconciliation is separate'}

def get_decision(complaint_id):
    rows=db.read_only('SELECT complaint_id,relevance,class_method,db_last_updated_at FROM src_complaint WHERE complaint_id=%s',(complaint_id,))
    if not rows: raise ApiError(404,'complaint_not_found','민원 ID가 없습니다')
    row=rows[0]
    reviews=db.read_only("SELECT changed_by_user AS reviewer_id, changed_column FROM src_complaint_change WHERE complaint_id=%s AND changed_by_type='사람' AND changed_column='class_method' ORDER BY changed_by_user DESC LIMIT 2",(complaint_id,))
    return {'complaint_id':complaint_id,'relevance':row['relevance'],
            'class_method':row['class_method'],'review_evidence':bool(reviews),
            'verified_human_decision':row['class_method']=='사람' and len(reviews)==1,
            'population_confirmed':False}


def review_queue(*, limit: int = 25, offset: int = 0, gu: str | None = None) -> dict:
    """Read-only, operator-authenticated work queue; never bulk-marks AI rows reviewed."""
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or not 0 <= offset <= 281153:
        raise ApiError(422, 'invalid_paging', '페이지 크기 또는 시작 위치가 잘못됐습니다')
    where = "(class_method IS NULL OR class_method <> '사람')"
    params: list = []
    if gu is not None:
        if not gu.strip() or len(gu) > 30:
            raise ApiError(422, 'invalid_gu', '구 이름이 잘못됐습니다')
        where += ' AND gu = %s'
        params.append(gu)
    count_sql = 'SELECT COUNT(*) AS n FROM src_complaint WHERE ' + where
    count_rows = db.read_only(count_sql, tuple(params))
    sql = ('SELECT complaint_id,gid,gu,received_date,masked_summary,relevance,ped_type,class_method '
           'FROM src_complaint WHERE ' + where + ' ORDER BY complaint_id LIMIT %s OFFSET %s')
    records = db.read_only(sql, tuple(params + [limit, offset]))
    return {'rows': records, 'total_pending': int(count_rows[0]['n']),
            'limit': limit, 'offset': offset,
            'scope': 'C08_REVIEW_QUEUE_NOT_APPROVED', 'population_confirmed': False,
            'c07_official_allowed': False}


def review_progress() -> dict:
    """Separate row label, recorded human method, and completeness; no invented approvals."""
    rows = db.read_only('''SELECT COUNT(*) AS population,
      SUM(CASE WHEN class_method = '사람' THEN 1 ELSE 0 END) AS human_method_rows,
      SUM(CASE WHEN class_method = '사람' AND relevance IN ('보행안전 관련','비관련')
               THEN 1 ELSE 0 END) AS decided_rows,
      SUM(CASE WHEN class_method IS NULL OR class_method <> '사람' THEN 1 ELSE 0 END) AS pending_rows
      FROM src_complaint''')
    values = rows[0] if rows else {}
    return {'population': int(values.get('population') or 0),
            'human_method_rows': int(values.get('human_method_rows') or 0),
            'decided_rows_unverified': int(values.get('decided_rows') or 0),
            'pending_rows': int(values.get('pending_rows') or 0),
            'population_confirmed': False,
            'reason': 'No source snapshot plus per-row reviewer evidence reconciliation',
            'c07_official_allowed': False}
