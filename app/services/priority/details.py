"""DDL-free durable five-field evidence using immutable content-addressed files.

Store complete details on the backend's persistent volume, place a short
`ev1:<sha256>` pointer in 78.note. Missing or damaged evidence is an error.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from decimal import Decimal

FIELDS = ('domain_scores', 'indicator_contributions', 'unevaluated_reasons',
          'confidence_grade', 'score_excluding_accidents')
PREFIX = 'ev1:'


def _root():
    path = os.environ.get('RADAR_PRIORITY_EVIDENCE_DIR')
    if not path:
        raise RuntimeError('RADAR_PRIORITY_EVIDENCE_DIR must point to a persistent, backed-up server volume')
    return Path(path).expanduser().resolve()


def _default(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(type(value).__name__)


def _payload(run_id, gid, data):
    if type(run_id) is not int or run_id <= 0 or not isinstance(gid, str) or not gid.strip():
        raise ValueError('invalid candidate identity')
    if not isinstance(data, dict) or set(data) != set(FIELDS):
        raise ValueError('five detail fields required')
    for name in ('domain_scores', 'indicator_contributions'):
        value = data[name]
        if value is not None and not isinstance(value, dict):
            raise ValueError('invalid ' + name)
        for num in (value or {}).values():
            if num is None:
                continue
            if isinstance(num, bool) or not isinstance(num, (int, float, Decimal)):
                raise ValueError('invalid numeric detail')
            n = Decimal(str(num))
            if not n.is_finite() or not 0 <= n <= 100:
                raise ValueError('invalid numeric detail')
    if data['unevaluated_reasons'] is not None and not isinstance(data['unevaluated_reasons'], (dict, list)):
        raise ValueError('invalid unevaluated_reasons')
    if data['confidence_grade'] is not None and not isinstance(data['confidence_grade'], str):
        raise ValueError('invalid confidence_grade')
    if data['score_excluding_accidents'] is not None:
        v = Decimal(str(data['score_excluding_accidents']))
        if not v.is_finite() or not 0 <= v <= 100:
            raise ValueError('invalid accident-excluded score')
    return json.dumps({'run_id': run_id, 'gid': gid, **data}, ensure_ascii=False,
                      sort_keys=True, separators=(',', ':'), allow_nan=False, default=_default).encode('utf-8')


def store_evidence(run_id:int, gid:str, data:dict) -> str:
    """Write-once sidecar. Return a 68-character token for 78.note.

    File written before DB commit; a failed DB transaction may leave an orphan.
    Orphans cannot be served because readers require an existing 78 row.
    """
    raw = _payload(run_id,gid,data)
    digest = hashlib.sha256(raw).hexdigest()
    root = _root()
    path = root / digest[:2] / (digest+'.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('evidence file collision')
    else:
        import tempfile
        fd, temp_name = tempfile.mkstemp(dir=str(path.parent),prefix='.writing-')
        try:
            with os.fdopen(fd,'wb') as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_name,path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    return PREFIX+digest


def read_evidence(read_only, run_id:int, gid:str) -> dict:
    rows = read_only('SELECT note FROM priority_candidate WHERE run_id=%s AND gid=%s',(run_id,gid))
    if len(rows)!=1:
        raise ValueError('candidate evidence identity not found')
    note = rows[0].get('note') or ''
    if not note.startswith(PREFIX):
        return {'stored':False,**{k:None for k in FIELDS}}
    digest=note[len(PREFIX):]
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('invalid evidence pointer')
    raw = (_root() / digest[:2] / (digest+'.json')).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=digest:
        raise ValueError('evidence checksum mismatch')
    obj=json.loads(raw)
    if obj.get('run_id')!=run_id or obj.get('gid')!=gid or set(obj)!=set(FIELDS)|{'run_id','gid'}:
        raise ValueError('evidence identity mismatch')
    return {'stored':True, **{k:obj[k] for k in FIELDS}}


def encode_evidence(run_id, gid, data):
    raw = _payload(run_id,gid,data)
    return raw.decode('utf-8'),hashlib.sha256(raw).hexdigest()
