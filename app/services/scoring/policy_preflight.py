"""DB62 local evidence preflight. Never proposes, approves or registers DB rows."""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from app.services.scoring import setting_links as links
from app.services.scoring.d05_conditions import validate_d05_rule

class PolicyPreflightBlocked(ValueError):
    pass

MISSING_RULE = 'keep_base_no_complaint_adjustment'


def _read(raw):
    doc = json.loads(raw.decode('utf-8-sig'), object_pairs_hook=links._pairs,
                     parse_float=Decimal, parse_constant=links._invalid_constant)
    if not isinstance(doc, dict):
        raise PolicyPreflightBlocked('POLICY_OBJECT_REQUIRED')
    return doc


def _review_bytes(value):
    # A review representation of project's typed tuple, NOT a registration codec.
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False, default=lambda x: str(x) if isinstance(x, Decimal) else _bad_type(x)).encode()


def _bad_type(value):
    raise TypeError(type(value).__name__)


def preflight_policy(raw: bytes, *, expected_sha256: str) -> dict:
    actual = sha256(raw).hexdigest()
    if actual != expected_sha256:
        raise PolicyPreflightBlocked('POLICY_RAW_HASH_MISMATCH')
    doc = _read(raw)
    if (doc.get('inside_hazard_unobserved') != MISSING_RULE
            or doc.get('hazard_missing_rule_approved_by_user') is not True):
        raise PolicyPreflightBlocked('APPROVED_MISSING_RULE_REQUIRED')
    if doc.get('complaint_mode') != 'inside_hazard':
        raise PolicyPreflightBlocked('POLICY_MODE_MISMATCH')
    validate_d05_rule(doc.get('d05_rule'))
    projections = {kind: links.project(doc, kind) for kind in links.KINDS}
    removed = deepcopy(doc)
    del removed['inside_hazard_unobserved']
    if links.project(removed, '기준값') == projections['기준값']:
        raise PolicyPreflightBlocked('APPROVED_RULE_NOT_BOUND_TO_THRESHOLD')
    return {'status':'PASS', 'raw_sha256':actual, 'official_content_ref':'sha256:'+actual,
            'hash_authority':'RAW_BYTES_MATCH_EXISTING_SETTING_LINKS_READ_DOCUMENT',
            'review_components':{kind:{'namespace':'REVIEW_ONLY_TYPED_DECIMAL_AS_STRING_V1',
               'sha256':sha256(_review_bytes(value)).hexdigest(),
               'value':json.loads(_review_bytes(value))} for kind,value in projections.items()},
            'version_label':doc['policy']['label'], 'document_status':doc.get('document_status'),
            'db62_registered':False, 'approval_created':False, 'db_writes':0}


def compare_components(calculation_raw, component_raw_by_kind):
    if set(component_raw_by_kind) != set(links.KINDS):
        raise PolicyPreflightBlocked('THREE_COMPONENT_DOCUMENTS_REQUIRED')
    doc = _read(calculation_raw)
    # Missing/changed approved rule is blocked even when all three docs were changed.
    preflight_policy(calculation_raw, expected_sha256=sha256(calculation_raw).hexdigest())
    for kind in links.KINDS:
        other = _read(component_raw_by_kind[kind])
        if links.project(doc, kind) != links.project(other, kind):
            raise PolicyPreflightBlocked('COMPONENT_MISMATCH:'+kind)
    return True


def store_policy_evidence(raw, root, *, expected_sha256):
    report = preflight_policy(raw, expected_sha256=expected_sha256)
    path = Path(root) / 'policies' / (report['raw_sha256']+'.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('xb') as output:
            output.write(raw)
    except FileExistsError:
        if path.read_bytes() != raw:
            raise PolicyPreflightBlocked('IMMUTABLE_POLICY_EVIDENCE_CONFLICT')
    # The actual consumer validates byte digest, label and projection on readback.
    doc = links.read_document({'content_ref':report['official_content_ref'],
                              'version_label':report['version_label']}, root)
    if any(links.project(doc, kind) != links.project(_read(raw), kind) for kind in links.KINDS):
        raise PolicyPreflightBlocked('POLICY_READBACK_MISMATCH')
    return report
