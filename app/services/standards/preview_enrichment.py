"""F-01 display-only F-03/F-04 contract adapter prototype.

Do not treat this as an approved application patch. It requires the existing F03/F04
modules and authoritative grade/contact records before production integration.
"""
from collections.abc import Mapping


def enrich_f01_match(f01_result, *, grade_by_jurisdiction, official_directory,
                     describe_confidence, attach_contact):
    """Preserve F01 routing while enriching advisory display using verified inputs only.

    `grade_by_jurisdiction`: authority-reviewed grade records, keyed by JUR ID:
      { 'JUR-XX': {'basis_grade':'A', 'source_ref':'...'} }
    `official_directory`: authority-checked business team/representative contacts.
    """
    original = dict(f01_result)
    candidates = original.get('candidate_departments')
    if not isinstance(candidates, list):
        raise ValueError('invalid F01 candidate_departments')
    status = original.get('status')
    if status not in {'1차 부서 후보', '확인 필요', '담당 미정'}:
        raise ValueError('invalid F01 status')

    # F01's chosen candidate is advisory, never a confirmed department.
    eligible = status == '1차 부서 후보' and len(candidates) == 1
    single = candidates[0] if eligible else None
    jid = single.get('jurisdiction_id') if isinstance(single, Mapping) else None
    dept = single.get('dept_name') if isinstance(single, Mapping) else None
    eligible = eligible and isinstance(jid, str) and bool(jid) and isinstance(dept, str) and bool(dept.strip())
    grade = grade_by_jurisdiction.get(jid, {}) if eligible else {}
    if not isinstance(grade, Mapping):
        grade = {}
    validated_grade = grade.get('basis_grade')
    validated_source = grade.get('source_ref')
    if validated_grade not in ('A','B','C') or not isinstance(validated_source,str) or not validated_source.strip():
        validated_grade = None
        validated_source = None

    f03_in = {
        'status': '1차 부서 후보' if eligible else '확인 필요',
        'reason': 'F01 confirmed advisory match' if eligible else 'F01 unresolved or multiple candidates',
        'receiving_dept': dept if eligible else None,
        'gu_name': single.get('gu_name') if eligible else None,
        'matching_rules': ([{'jurisdiction_id': jid, 'basis_grade': validated_grade,
                             'source_ref': validated_source}] if eligible else []),
        'department_finalized': False,
    }
    confidence = describe_confidence(f03_in)
    contact = attach_contact(confidence, directory=official_directory)
    # Never overlay F01 status or routing data with display-enrichment status.
    result = dict(original)
    for field in ('basis_grade', 'confidence_label', 'confidence_reason',
                  'dept_team', 'dept_phone', 'contact_source_ref',
                  'contact_status', 'contact_reason', 'contact_type'):
        result[field] = contact.get(field)
    result['grade_source_ref'] = validated_source
    result['department_finalized'] = False
    return result
