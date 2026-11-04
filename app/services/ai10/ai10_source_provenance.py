"""AI-10 SRC 출처 검사 (DB 56 source_list 조회 결과를 사용; 읽기 전용).

주의: used_tables는 데이터셋 수준 설명이며 레코드/컬럼의 출처 증명이 아니다.
출처 미기재 근거에 SRC 번호를 자동 할당하지 않는다.
이 모듈은 외부 전송 허가를 내리지 않으며, llm_tasks.toml의 허용목록을 변경하지 않는다.
"""
from __future__ import annotations
import re
from typing import Any, Iterable, Mapping

_SRC_RE = re.compile(r"SRC\d+\Z")


def audit_evidence_sources(evidence_items: Iterable[Any], source_rows: Iterable[Mapping[str, Any]]) -> dict:
    """검증된 ID 목록과 미확정/불일치를 분리한다.

    source_rows: 운영 DB에서 SELECT source_id, access_level, used_tables FROM source_list로 조회한 결과.
    명시된 source_id의 존재 여부만 검증한다. 출처가 실제 해당 컬럼에 기여했는지는 별도 검증.
    """
    catalog = {row['source_id']: row for row in source_rows if isinstance(row.get('source_id'), str)}
    confirmed, issues = set(), []
    for index, evidence in enumerate(evidence_items, 1):
        item = evidence if isinstance(evidence, dict) else evidence.model_dump()
        sid = item.get('source_id')
        if not sid:
            issues.append({'index': index, 'status': 'source_id_missing', 'source_table': item.get('source_table'), 'source_column': item.get('source_column')})
        elif not isinstance(sid, str) or not _SRC_RE.fullmatch(sid):
            issues.append({'index': index, 'status': 'invalid_source_id', 'source_id': sid})
        elif sid not in catalog:
            issues.append({'index': index, 'status': 'not_in_source_list', 'source_id': sid})
        else:
            confirmed.add(sid)
            # DB 56의 '공개'는 법적 외부 전송 가능성을 단독 보증하지 않는다.
            access = catalog[sid].get('access_level')
            if access != '공개':
                issues.append({'index': index, 'status': 'external_review_required', 'source_id': sid, 'access_level': access})
    return {'catalog_matched_ids': sorted(confirmed), 'issues': issues, 'provenance_verified': False,
            'external_transfer_approved': False}
