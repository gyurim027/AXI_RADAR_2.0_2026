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
          'confidence_grade', 'score_excluding_accidents', 'exclusion_reasons',
          'complaint_contribution', 'policy_version')
LEGACY_FIELDS = FIELDS[:5]
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
    if not isinstance(data, dict) or set(data) not in (set(FIELDS), set(LEGACY_FIELDS)):
        raise ValueError('five legacy or eight detail fields required')
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
    if 'exclusion_reasons' in data and not isinstance(data['exclusion_reasons'], (list, dict)):
        raise ValueError('invalid exclusion reasons')
    if 'complaint_contribution' in data and data['complaint_contribution'] is not None:
        value = data['complaint_contribution']
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)) or not Decimal(str(value)).is_finite():
            raise ValueError('invalid complaint contribution')
    if 'policy_version' in data and (not isinstance(data['policy_version'], str) or not data['policy_version'].strip()):
        raise ValueError('invalid policy version')
    return json.dumps({'run_id': run_id, 'gid': gid, **data}, ensure_ascii=False,
                      sort_keys=True, separators=(',', ':'), allow_nan=False, default=_default).encode('utf-8')


def store_evidence(run_id:int, gid:str, data:dict, *, on_created=None) -> str:
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
            if on_created is not None:
                on_created(path, digest)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
    return PREFIX+digest


def cleanup_uncommitted_evidence(created):
    """Best-effort cleanup of files this transaction created, not pre-existing files.

    Only use after database rollback. A file is removed only if its content
    still hashes to the digest recorded at creation. Successful writes and
    pre-existing content-addressed files are never removed here.
    """
    for path, digest in reversed(created):
        try:
            path = Path(path)
            if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == digest:
                path.unlink()
        except OSError:
            # Cleanup failure must not hide the original transaction failure.
            # Orphans are not publicly readable without a committed 78 pointer.
            pass


def _unique_json_pairs(pairs):
    """Reject ambiguous evidence documents rather than accepting the last duplicate key."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate evidence JSON key: ' + key)
        result[key] = value
    return result


def read_legacy_evidence(read_only, run_id:int, gid:str) -> dict:
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
    obj=json.loads(raw, object_pairs_hook=_unique_json_pairs)
    if obj.get('run_id')!=run_id or obj.get('gid')!=gid or (set(obj) - {'run_id','gid'}) not in (set(FIELDS), set(LEGACY_FIELDS)):
        raise ValueError('evidence identity mismatch')
    return {'stored':True, 'evidence_version': 'EIGHT' if set(FIELDS) <= set(obj) else 'LEGACY_FIVE',
            **{k:obj.get(k) for k in FIELDS}}


def encode_evidence(run_id, gid, data):
    raw = _payload(run_id,gid,data)
    return raw.decode('utf-8'),hashlib.sha256(raw).hexdigest()


def read_evidence(read_only, run_id, gid):
    """DB78_EXPLICIT_STORAGE_ROUTING_V1.

    An ev1: pointer names immutable legacy sidecar evidence; never silently
    substitute DB8 data if that evidence is missing or has a bad checksum.
    Candidates without an ev1: pointer use the 8-column DB78 contract.
    An old note-only read adapter with no pointer stays unverified, not valid.
    """
    from app.services.priority.db8_details import COLS, decode_db_row, DetailBlocked
    if type(run_id) is not int or run_id <= 0 or not isinstance(gid, str) or not gid.strip():
        raise ValueError('invalid candidate identity')
    args = (run_id, gid)
    notes = read_only('SELECT note FROM priority_candidate WHERE run_id=%s AND gid=%s', args)
    if len(notes) != 1:
        raise ValueError('candidate evidence identity not found')
    note = notes[0].get('note')
    if isinstance(note, str) and note.startswith(PREFIX):
        # Explicit legacy representation. Checksum/identity errors must propagate.
        return read_legacy_evidence(lambda _sql, _args: notes, run_id, gid)
    rows = read_only('SELECT '+','.join(COLS)+' FROM priority_candidate WHERE run_id=%s AND gid=%s', args)
    if len(rows) != 1:
        raise DetailBlocked('CANDIDATE_IDENTITY_NOT_FOUND')
    row = rows[0]
    if all(col in row for col in COLS):
        return decode_db_row(row)
    if set(row) == {'note'} and not (isinstance(row['note'], str) and row['note'].startswith(PREFIX)):
        # Compatibility with a legacy note-only reader. This is not verified.
        return {'stored': False, 'evidence_version': 'UNSTORED',
                'complete': False, **{k: None for k in FIELDS}}
    raise DetailBlocked('DB78_EIGHT_DETAIL_COLUMNS_MISSING')
