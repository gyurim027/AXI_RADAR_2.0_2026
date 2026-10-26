"""C08 evidence -> C07 confirmed-row contract. No implicit approvals.

The src_complaint human marker alone is insufficient: the matching change-ledger
entry must exist. Full source is preserved; uncertain rows stay INCOMPLETE.
"""
from __future__ import annotations
from datetime import date
from app.core.db import read_only
from app.services.c07.rolling_contract import build_contract

SOURCE_SQL = """SELECT s.complaint_id,s.gid,s.coord_accuracy,s.relevance,s.class_method,
 s.received_date,s.source_type,s.report_type_raw,s.ped_type,
 (SELECT COUNT(*) FROM src_complaint_change ch
   WHERE ch.complaint_id=s.complaint_id
     AND ch.changed_column='class_method'
     AND ch.changed_by_type='사람'
     AND ch.new_value='사람') AS reviewer_audit_count
 FROM src_complaint s ORDER BY s.complaint_id"""


def canonical_c07_row(raw):
    """Requires stored human decision AND one matching reviewer change event."""
    r=dict(raw)
    evidence=(r.get('class_method')=='사람' and
              r.get('reviewer_audit_count') == 1)
    if evidence and r.get('relevance')=='보행안전 관련':
        r['review_status']='CONFIRMED';r['relevance']='Y'
    elif evidence and r.get('relevance')=='비관련':
        r['review_status']='CONFIRMED';r['relevance']='N'
    else:
        r['review_status']='UNREVIEWED';r['relevance']=None
    return r


def c07_from_live_c08(*, start=date(2021,1,1), end=date(2026,9,30)):
    gids=[str(row['ID_gid']) for row in read_only('SELECT ID_gid FROM grid_feature ORDER BY ID_gid')]
    originals=read_only(SOURCE_SQL)
    rows=[canonical_c07_row(r) for r in originals]
    result=build_contract(rows,gids,earliest=start,through=end)
    confirmed=sum(r['review_status']=='CONFIRMED' for r in rows)
    result['manifest']['human_confirmed_rows']=confirmed
    result['manifest']['unconfirmed_rows']=len(rows)-confirmed
    result['manifest']['source_population_complete']=confirmed==len(rows)
    result['manifest']['c07_for_official_score_allowed']=bool(rows) and confirmed==len(rows)
    result['manifest']['human_evidence_contract']='src_complaint.class_method + exactly_one src_complaint_change class_method human event'
    result['manifest']['authority']='C08_HUMAN_ROW_ONLY_NOT_AI01'
    return result
