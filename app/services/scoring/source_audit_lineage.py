"""R03 aggregate audit identity and existing DB77.note binding. No DB access.

The hash proves the aggregate audit, not the original 281153-row source snapshot.
Neither this receipt nor persistence can promote approved_for_official_write.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import re
from app.services.scoring.r02_full_source_quarantine import UNMAPPED_POLICY_ID
from app.services.scoring.r02_explicit_exclusion import POLICY_ID
from app.services.scoring.setting_links import _pairs, _invalid_constant

class SourceAuditBlocked(ValueError):
    pass


def valid_hash(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise SourceAuditBlocked('INVALID_SOURCE_AUDIT_HASH')
    return value


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(',', ':'), allow_nan=False).encode()

@dataclass(frozen=True)
class SourceAudit:
    raw: bytes
    audit_sha256: str
    period_start: date
    period_end: date
    grid_count: int


def verify_source_audit(raw, *, expected_sha256, start, end, grid_count=None):
    valid_hash(expected_sha256)
    doc = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=_pairs,
                     parse_constant=_invalid_constant)
    if not isinstance(doc, dict):
        raise SourceAuditBlocked('AUDIT_OBJECT_REQUIRED')
    audit = doc.get('audit', doc)
    if not isinstance(audit, dict):
        raise SourceAuditBlocked('AUDIT_OBJECT_REQUIRED')
    payload = {k:v for k,v in audit.items() if k != 'audit_sha256'}
    if sha256(_canonical(payload)).hexdigest() != expected_sha256 or audit.get('audit_sha256') != expected_sha256:
        raise SourceAuditBlocked('SOURCE_AUDIT_HASH_MISMATCH')
    if (audit.get('policy_mapped') != POLICY_ID or audit.get('policy_unmapped') != UNMAPPED_POLICY_ID
            or audit.get('approved_for_official_write') is not False
            or audit.get('classification_modified') is not False
            or audit.get('grid_assignment_modified') is not False):
        raise SourceAuditBlocked('SOURCE_AUDIT_SCOPE_MISMATCH')
    if type(start) is not date or type(end) is not date or start > end:
        raise SourceAuditBlocked('INVALID_SOURCE_AUDIT_PERIOD')
    if audit.get('period_start') != start.isoformat() or audit.get('period_end') != end.isoformat():
        raise SourceAuditBlocked('SOURCE_AUDIT_PERIOD_MISMATCH')
    names=('source_rows','mapped_rows','mapped_eligible_rows','mapped_excluded_rows',
           'unmapped_quarantined_rows','grid_count','prepared_grid_count')
    if any(type(audit.get(k)) is not int or audit[k] < 0 for k in names):
        raise SourceAuditBlocked('SOURCE_AUDIT_COUNTS_INVALID')
    if (audit['source_rows'] != audit['mapped_rows']+audit['unmapped_quarantined_rows']
            or audit['mapped_rows'] != audit['mapped_eligible_rows']+audit['mapped_excluded_rows']
            or audit['grid_count'] <= 0 or audit['prepared_grid_count'] != audit['grid_count']
            or (grid_count is not None and audit['grid_count'] != grid_count)):
        raise SourceAuditBlocked('SOURCE_AUDIT_COUNTS_MISMATCH')
    valid_hash(audit.get('mapped_excluded_sha256'))
    valid_hash(audit.get('unmapped_quarantined_sha256'))
    return SourceAudit(_canonical(audit), expected_sha256, start, end, audit['grid_count'])


def revalidate_source_audit(receipt, *, start, end):
    if not isinstance(receipt, SourceAudit):
        raise SourceAuditBlocked('VERIFIED_SOURCE_AUDIT_REQUIRED')
    return verify_source_audit(receipt.raw, expected_sha256=receipt.audit_sha256,
                               start=start, end=end, grid_count=receipt.grid_count)


def source_audit_note(sha):
    return 'r03:'+valid_hash(sha)


def store_source_audit(receipt, root):
    checked = revalidate_source_audit(receipt, start=receipt.period_start, end=receipt.period_end)
    path = Path(root)/'audits'/(checked.audit_sha256+'.json')
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('xb') as file:
            file.write(checked.raw)
    except FileExistsError:
        if path.read_bytes() != checked.raw:
            raise SourceAuditBlocked('IMMUTABLE_SOURCE_AUDIT_CONFLICT')
    verify_source_audit(path.read_bytes(),expected_sha256=checked.audit_sha256,
                        start=checked.period_start,end=checked.period_end)
    return path


def verify_run_binding(run_id, note, receipt):
    if type(run_id) is not int or run_id <= 1:
        raise SourceAuditBlocked('LEGACY_RUN1_SOURCE_LINK_BLOCKED')
    checked = revalidate_source_audit(receipt, start=receipt.period_start,end=receipt.period_end)
    if note != source_audit_note(checked.audit_sha256):
        raise SourceAuditBlocked('RUN_SOURCE_AUDIT_MISMATCH')
    return {'run_id':run_id, 'source_audit_sha256':checked.audit_sha256,
            'aggregate_audit_verified':True, 'source_snapshot_verified':False}


def read_source_lineage(run_id, root, reader):
    """Read one nonlegacy run and verify its locally persisted aggregate audit.

    Reader must be explicitly injected; this function never creates a DB connection.
    No DB59/source snapshot claim is made from a matching aggregate audit hash.
    """
    if type(run_id) is not int or run_id <= 1:
        raise SourceAuditBlocked('LEGACY_RUN1_SOURCE_LINK_BLOCKED')
    rows = reader('SELECT run_id,note,period_start,period_end FROM priority_run WHERE run_id=%s', (run_id,))
    if len(rows) != 1 or rows[0].get('run_id') != run_id:
        raise SourceAuditBlocked('SOURCE_LINEAGE_RUN_NOT_FOUND')
    row = rows[0]
    note = row.get('note')
    if not isinstance(note, str) or not note.startswith('r03:'):
        raise SourceAuditBlocked('SOURCE_LINEAGE_REFERENCE_MISSING')
    sha = valid_hash(note[4:])
    path = Path(root)/'audits'/(sha+'.json')
    receipt = verify_source_audit(path.read_bytes(),expected_sha256=sha,
                                  start=row['period_start'],end=row['period_end'])
    return verify_run_binding(run_id,note,receipt)
