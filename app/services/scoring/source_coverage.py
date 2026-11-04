"""Full-source coverage contract for a verified official run.
Unmapped source rows are explicitly excluded from spatial scoring, never set to zero.
Every mapped source row must have a separately human-confirmed review export row.
"""
from __future__ import annotations
from hashlib import sha256
import json
from app.services.scoring.approved_inputs import classification_decision

class CoverageBlocked(ValueError):
    pass

def verify_coverage(source_rows, reviewed_rows, valid_gids):
    """Pure check of exact complaint IDs, source mapping and export completeness.
    source_rows: full period rows from src_complaint with complaint_id,gid.
    Returns an aggregate manifest without personal information or raw IDs.
    """
    valid_gids = {str(x) for x in valid_gids}
    source_by_id = {}
    for row in source_rows:
        cid = str(row.get('complaint_id') or '').strip()
        if not cid or cid in source_by_id:
            raise CoverageBlocked('INVALID_OR_DUPLICATE_SOURCE_ID')
        source_by_id[cid] = row
    mapped_ids = set()
    unmapped_ids = set()
    for cid, row in source_by_id.items():
        gid = row.get('gid')
        if gid is None or str(gid) not in valid_gids:
            unmapped_ids.add(cid)
        else:
            mapped_ids.add(cid)
    reviewed_ids = set()
    unresolved_ids = set()
    for row in reviewed_rows:
        cid = str(row.get('complaint_id') or '').strip()
        if not cid or cid in reviewed_ids:
            raise CoverageBlocked('DUPLICATE_OR_EMPTY_REVIEW_ID')
        reviewed_ids.add(cid)
        if cid not in mapped_ids:
            raise CoverageBlocked('REVIEWED_ID_NOT_IN_MAPPED_SOURCE')
        source_gid = str(source_by_id[cid]['gid'])
        if str(row.get('gid')) != source_gid:
            raise CoverageBlocked('REVIEW_GID_SOURCE_MISMATCH')
        if classification_decision(row) is None:
            unresolved_ids.add(cid)
    if reviewed_ids != mapped_ids:
        raise CoverageBlocked('MAPPED_SOURCE_NOT_FULLY_REVIEWED:missing=%d,extra=%d' %
                              (len(mapped_ids - reviewed_ids),len(reviewed_ids - mapped_ids)))
    digest = lambda ids: sha256(('\n'.join(sorted(ids))+'\n').encode('utf-8')).hexdigest()
    return {'contract':'R01_SPATIAL_MAPPING_EXCLUSION_V1',
            'source_count':len(source_by_id),'mapped_count':len(mapped_ids),
            'unmapped_excluded_count':len(unmapped_ids),
            'mapped_ids_sha256':digest(mapped_ids),
            'excluded_ids_sha256':digest(unmapped_ids),
            'exclusion_reason':'NO_VALID_GRID_ID_FOR_SPATIAL_SCORING',
            'unmapped_used_in_scoring':False,
            'reviewed_mapped_count':len(reviewed_ids),
            'unresolved_mapped_count':len(unresolved_ids),
            'classification_status':'INCOMPLETE' if unresolved_ids else 'COMPLETE'}
