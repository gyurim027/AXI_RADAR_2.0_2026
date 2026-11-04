"""D-05 condition evaluation. No inferred or default thresholds.

Only a separately reviewed rule embedded in the immutable policy document can
produce Y/N condition values. Missing observation remains unknown (NULL), never N.
This module is pure and performs no database access.
"""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
from math import isfinite

from app.services.scoring.approved_inputs import InputBlocked

ROLES = ('hazard', 'exposure', 'vulnerability')
COLS = {'hazard':'cond_hazard_yn','exposure':'cond_exposure_yn',
        'vulnerability':'cond_vulnerable_yn'}


def validate_d05_rule(rule):
    """Require an explicit policy version, all thresholds, and combining operator.

    Thresholds apply to normalized 0..1 domain values. They are *not* guessed
    from the 70-point candidate threshold or confidence grade.
    """
    if not isinstance(rule,dict) or set(rule) != {'version','operator','thresholds','missing'}:
        raise InputBlocked('D05_RULE_REQUIRED_OR_INCOMPLETE')
    if not isinstance(rule['version'],str) or not rule['version'].strip():
        raise InputBlocked('D05_RULE_VERSION_REQUIRED')
    if rule['operator'] not in ('ANY','ALL') or rule['missing'] != 'UNKNOWN':
        raise InputBlocked('D05_UNSUPPORTED_OPERATOR_OR_MISSING_POLICY')
    thresholds=rule['thresholds']
    if not isinstance(thresholds,dict) or set(thresholds)!=set(ROLES):
        raise InputBlocked('D05_THRESHOLDS_INCOMPLETE')
    for role in ROLES:
        value=thresholds[role]
        if isinstance(value,bool):raise InputBlocked('D05_INVALID_THRESHOLD')
        try: n=Decimal(str(value))
        except (InvalidOperation,TypeError,ValueError) as exc:
            raise InputBlocked('D05_INVALID_THRESHOLD') from exc
        if not n.is_finite() or not Decimal(0)<=n<=Decimal(1):
            raise InputBlocked('D05_INVALID_THRESHOLD')
    return rule


def evaluate_d05(domains, rule):
    """Tri-state role evaluation. Result NULL when insufficient information.

    ANY: Y if any Y, N if all N, else NULL.
    ALL: N if any N, Y if all Y, else NULL.
    matched_roles records positive domain conditions only, never unknowns.
    """
    validate_d05_rule(rule)
    if not isinstance(domains,dict) or not set(ROLES)<=set(domains):
        raise InputBlocked('D05_DOMAIN_INPUTS_INCOMPLETE')
    statuses={}
    for role in ROLES:
        raw=domains[role]
        if raw is None or (isinstance(raw,float) and raw!=raw):
            statuses[role]=None
            continue
        if isinstance(raw,bool):raise InputBlocked('D05_INVALID_DOMAIN_VALUE')
        try: n=Decimal(str(raw))
        except (InvalidOperation,TypeError,ValueError) as exc:
            raise InputBlocked('D05_INVALID_DOMAIN_VALUE') from exc
        if not n.is_finite() or not Decimal(0)<=n<=Decimal(1):
            raise InputBlocked('D05_INVALID_DOMAIN_VALUE')
        statuses[role]='Y' if n>=Decimal(str(rule['thresholds'][role])) else 'N'
    vals=list(statuses.values())
    if rule['operator']=='ANY':
        result='Y' if 'Y' in vals else ('N' if all(v=='N' for v in vals) else None)
    else:
        result='N' if 'N' in vals else ('Y' if all(v=='Y' for v in vals) else None)
    matched=','.join(role for role in ROLES if statuses[role]=='Y')
    return {'cond_result_yn':result, **{COLS[k]:statuses[k] for k in ROLES},
            'matched_roles':matched if matched else ('' if result is not None else None)}


def verify_d05_persisted_conditions(candidate, rule):
    """Check 78 condition fields match the approved ANY/ALL tri-state rule.

    NULL is a valid UNKNOWN observation, not a fabricated N. A contradictory
    candidate is rejected before any 77/78 writer is invoked.
    """
    validate_d05_rule(rule)
    required=('cond_result_yn','cond_hazard_yn','cond_exposure_yn',
              'cond_vulnerable_yn','matched_roles')
    if any(k not in candidate for k in required):
        raise InputBlocked('D05_CANDIDATE_FIELDS_MISSING')
    roles={role:candidate[COLS[role]] for role in ROLES}
    if any(v not in ('Y','N',None) for v in roles.values()):
        raise InputBlocked('D05_INVALID_ROLE_RESULT')
    vals=list(roles.values())
    if rule['operator']=='ANY':
        expected='Y' if 'Y' in vals else ('N' if all(v=='N' for v in vals) else None)
    else:
        expected='N' if 'N' in vals else ('Y' if all(v=='Y' for v in vals) else None)
    matched=','.join(role for role in ROLES if roles[role]=='Y')
    expected_matched=matched if matched else ('' if expected is not None else None)
    if candidate['cond_result_yn'] != expected or candidate['matched_roles'] != expected_matched:
        raise InputBlocked('D05_CANDIDATE_CONDITION_MISMATCH')
    return True
