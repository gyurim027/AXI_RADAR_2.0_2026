"""C-08 type pre-review, deliberately separate from post-classification sampling.

Local audit/preview only; this is NOT an operational authentication or approval route.
Uses a sidecar sqlite DB. The Q3 281153-row candidate DB stays read-only.
"""
from __future__ import annotations
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

VALID = {'보행안전 관련', '비관련'}
DDL = '''CREATE TABLE IF NOT EXISTS type_prereview_event(
 event_id INTEGER PRIMARY KEY AUTOINCREMENT,
 complaint_id TEXT NOT NULL, source_sha256 TEXT NOT NULL,
 rule_sha256 TEXT NOT NULL, proposed TEXT NOT NULL,
 decision TEXT NOT NULL, reviewer_ref TEXT NOT NULL,
 reason TEXT NOT NULL, event_utc TEXT NOT NULL,
 previous_event_sha256 TEXT NOT NULL, event_sha256 TEXT NOT NULL UNIQUE,
 scope TEXT NOT NULL CHECK(scope='TYPE_ONLY_LOCAL_UNAUTHENTICATED'))'''


def snapshot_id(candidate_path):
    """Fingerprints actual candidate DB bytes; changing candidates blocks old reviews."""
    h = hashlib.sha256()
    with open(candidate_path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _row(candidate_con, complaint_id):
    return candidate_con.execute('SELECT complaint_id,gid,received_date,type_rule_tier,type_candidate,rule_sha256 FROM q3_row WHERE complaint_id=?', (complaint_id,)).fetchone()


def append_local_event(candidate_path, ledger_path, complaint_id, decision, reviewer_ref, reason):
    """Append evidence only; cannot create a production-approved decision."""
    if decision not in VALID or not str(reviewer_ref).strip() or len(str(reason).strip()) < 8:
        raise ValueError('INVALID_REVIEW_INPUT')
    candidate_path, ledger_path = Path(candidate_path), Path(ledger_path)
    if not candidate_path.exists(): raise FileNotFoundError(candidate_path)
    source_sha = snapshot_id(candidate_path)
    with closing(sqlite3.connect(f'file:{candidate_path.as_posix()}?mode=ro', uri=True)) as source:
        row = _row(source, complaint_id)
    if not row: raise ValueError('UNKNOWN_COMPLAINT')
    _, gid, date, tier, proposed, rule_sha = row
    if tier == 'RULE_CONFLICT': raise ValueError('CONFLICT_REQUIRES_OTHER_EVIDENCE')
    if tier != 'TYPE_DEFAULT_ONLY' or proposed not in VALID: raise ValueError('INSUFFICIENT_TYPE_EVIDENCE')
    if proposed != decision: raise ValueError('CANNOT_OVERRIDE_TYPE_WITHOUT_SOURCE_TEXT')
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(ledger_path)) as ledger:
        ledger.execute(DDL)
        ledger.execute('BEGIN IMMEDIATE')
        existing = ledger.execute('SELECT 1 FROM type_prereview_event WHERE complaint_id=? LIMIT 1', (complaint_id,)).fetchone()
        if existing: raise ValueError('REVIEW_ALREADY_EXISTS')
        last = ledger.execute('SELECT event_sha256 FROM type_prereview_event ORDER BY event_id DESC LIMIT 1').fetchone()
        previous = last[0] if last else 'GENESIS'
        payload = dict(complaint_id=str(complaint_id),source_sha256=source_sha,rule_sha256=rule_sha,
                       proposed=proposed,decision=decision,reviewer_ref=str(reviewer_ref),reason=str(reason),
                       event_utc=datetime.now(timezone.utc).isoformat(),previous_event_sha256=previous,
                       scope='TYPE_ONLY_LOCAL_UNAUTHENTICATED')
        digest = hashlib.sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        ledger.execute('INSERT INTO type_prereview_event(complaint_id,source_sha256,rule_sha256,proposed,decision,reviewer_ref,reason,event_utc,previous_event_sha256,event_sha256,scope) VALUES(?,?,?,?,?,?,?,?,?,?,?)', (payload['complaint_id'],payload['source_sha256'],payload['rule_sha256'],payload['proposed'],payload['decision'],payload['reviewer_ref'],payload['reason'],payload['event_utc'],payload['previous_event_sha256'],digest,payload['scope']))
        ledger.commit()
        return dict(event_sha256=digest, scope=payload['scope'], official_approval=False)


def reconcile(candidate_path, ledger_path, start, end):
    """Source-wide reconciliation, local pre-review counts only. Official count hard-zero."""
    path=Path(candidate_path); sha=snapshot_id(path)
    with closing(sqlite3.connect(f'file:{path.as_posix()}?mode=ro',uri=True)) as src:
        total=src.execute('SELECT COUNT(*) FROM q3_row').fetchone()[0]
        eligible=src.execute('SELECT COUNT(*) FROM q3_row WHERE gid IS NOT NULL AND received_date BETWEEN ? AND ?', (start,end)).fetchone()[0]
        source_ids={r[0]:r for r in src.execute('SELECT complaint_id,gid,received_date,type_candidate,rule_sha256,type_rule_tier FROM q3_row')}
    local=0; valid=0; invalid=[]; per_grid={}
    if Path(ledger_path).exists():
        with closing(sqlite3.connect(ledger_path)) as ledger:
            rows=ledger.execute('SELECT complaint_id,source_sha256,rule_sha256,proposed,decision,reviewer_ref,reason,event_utc,previous_event_sha256,event_sha256,scope FROM type_prereview_event ORDER BY event_id').fetchall()
        local=len(rows); previous='GENESIS'; seen=set()
        for fields in rows:
            cid,ss,rs,p,d,who,why,stamp,prev,digest,scope=fields
            data=dict(complaint_id=cid,source_sha256=ss,rule_sha256=rs,proposed=p,decision=d,reviewer_ref=who,reason=why,event_utc=stamp,previous_event_sha256=prev,scope=scope)
            expected=hashlib.sha256(json.dumps(data,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
            row=source_ids.get(cid)
            if (expected!=digest or prev!=previous or ss!=sha or cid in seen or not row or
                scope!='TYPE_ONLY_LOCAL_UNAUTHENTICATED' or row[3]!=p or row[4]!=rs or
                row[5]!='TYPE_DEFAULT_ONLY' or d!=p):
                invalid.append(cid)
            else:
                _,gid,date,_,_,_=row
                if gid is not None and date is not None and start<=date<=end:
                    target=per_grid.setdefault(str(gid), {'local_related':0,'local_unrelated':0})
                    target['local_related' if d=='보행안전 관련' else 'local_unrelated']+=1
                valid+=1
            previous=digest;seen.add(cid)
    if invalid: raise ValueError('LEDGER_INTEGRITY_OR_SOURCE_CHANGED:'+','.join(map(str,invalid[:5])))
    matched=sum(g['local_related']+g['local_unrelated'] for g in per_grid.values())
    if matched>eligible: raise AssertionError('COUNTS_MISMATCH')
    return {'status':'TYPE_PREREVIEW_LOCAL_ONLY','source_rows':total,'period_assigned_rows':eligible,
            'local_events':local,'verified_local_events':valid,'period_local_reviewed':matched,
            'period_unreviewed':eligible-matched,'local_grid_summary':per_grid,
            'official_c08_verified_count':0,'c07_official_allowed':False,'mysql_writes':0}
