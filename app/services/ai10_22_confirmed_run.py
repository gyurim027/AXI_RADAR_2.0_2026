"""22건 샘플의 외부 확정 CK 전달 통합 점검. CK 추론/생성 및 실제 API/DB 호출 없음.

상위 기능이 확정한 CK 판정만 입력받아 기존 승인 문장 연결부를 호출한다.
기본 샘플의 ck_candidate는 잠정값이므로 절대 확정 입력으로 승격하지 않는다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from app.services.ai10_confirmed_ck_handoff import handoff_confirmed_ck
from app.services.ai10_operator_review import STORE

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / 'data' / 'RADAR_AI10_민원샘플_정리_v2.json'


def run_22_confirmed_handoff(
    records: list[dict[str, Any]],
    confirmed_inputs: dict[str, dict[str, Any]] | None = None,
    *,
    store: Path = STORE,
) -> dict[str, Any]:
    """상위 기능의 확인 결과만 연결. 식별 불가 입력은 오류로 즉시 거절한다."""
    if not isinstance(records, list):
        raise ValueError('샘플 목록이 아닙니다')
    if not isinstance(confirmed_inputs, dict) and confirmed_inputs is not None:
        raise ValueError('판정 입력은 sample_id별 객체여야 합니다')
    inputs = confirmed_inputs or {}
    ids = [rec.get('sample_id') for rec in records]
    if any(not isinstance(x, str) or not x.strip() for x in ids) or len(set(ids)) != len(ids):
        raise ValueError('샘플 ID 누락 또는 중복')
    unknown = set(inputs) - set(ids)
    if unknown:
        raise ValueError('알 수 없는 샘플 ID: ' + ', '.join(sorted(unknown)))
    rows = []
    for record in records:
        sid = record['sample_id']
        incoming = inputs.get(sid)
        if incoming is None:
            rows.append({'sample_id': sid, 'ck_provisional': record.get('ck_candidate'),
                         'confirmed_rule_id': None, 'status': '확정 판정 미제공',
                         'proposal': None, 'gemini_invoked': False})
            continue
        if not isinstance(incoming, dict):
            raise ValueError(f'{sid}: 판정 입력은 객체여야 합니다')
        # 샘플 텍스트/추정 CK를 판정 근거로 사용하지 않음.
        external = {key: incoming.get(key) for key in ('rule_id', 'judgment_confirmed', 'evidence_ref')}
        result = handoff_confirmed_ck(external,
            confirmed_department=incoming.get('confirmed_department'),
            confirmed_legal_basis=incoming.get('confirmed_legal_basis'), store=store)
        rows.append({'sample_id': sid, 'ck_provisional': record.get('ck_candidate'),
                     'confirmed_rule_id': result['rule_id'] if result['proposal'] is not None else None,
                     'status': result['status'], 'proposal': result['proposal'],
                     'gemini_invoked': False})
    return {'counts': {'total': len(rows),
                       'confirmed_inputs': len(inputs),
                       'linked': sum(row['proposal'] is not None for row in rows),
                       'not_linked': sum(row['proposal'] is None for row in rows)},
            'records': rows,
            'note': '기존 승인 문장을 연결하는 검증. 원문·AI 추론·Gemini·DB 호출·승인 상태 변경 없음'}


def main() -> None:
    parser = argparse.ArgumentParser(description='22건 확정 CK 입력·승인 문장 연결 검사')
    parser.add_argument('--confirmed-json', type=Path, help='상위 기능에서 검증한 {sample_id: {rule_id, judgment_confirmed, evidence_ref, ...}} JSON')
    parser.add_argument('--store', type=Path, default=STORE, help='기존 승인 문장 JSON 경로')
    args = parser.parse_args()
    records = json.loads(SAMPLES.read_text(encoding='utf-8-sig'))['records']
    inputs = None
    if args.confirmed_json:
        inputs = json.loads(args.confirmed_json.read_text(encoding='utf-8-sig'))
    result = run_22_confirmed_handoff(records, inputs, store=args.store)
    for row in result['records']:
        print(f"{row['sample_id']} | {row['status']} | {row['confirmed_rule_id'] or '-'}")
    c = result['counts']
    print(f"결과: {c['total']}건 / 연결 {c['linked']}건 / 미연결 {c['not_linked']}건 | Gemini/DB 미호출")


if __name__ == '__main__':
    main()
