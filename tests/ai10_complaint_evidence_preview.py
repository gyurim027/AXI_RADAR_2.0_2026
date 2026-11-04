"""AI-10 민원 사례별 근거 추적 미리보기. DB/Gemini 불사용, 운영 출력 아님.

배치: tests/ai10_complaint_evidence_preview.py
실행: uv run python tests/ai10_complaint_evidence_preview.py --id SAMPLE-01
전체: uv run python tests/ai10_complaint_evidence_preview.py --all
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SAMPLES = DATA / "RADAR_AI10_민원샘플_정리_v1.json"
RULES = DATA / "ai10_ck_rules_v0.4.json"


def preview(record, rule):
    out = [
        f"[{record['sample_id']}] 원본 번호 {record['source_row_number']} | {record['sanitized_title']}",
        f"신고일: {record['registered_date']} | 시험 분류: {record['ai10_test_scope']}",
        f"① 민원에서 가져온 내용(신고인의 주장): {record['complaint_claim_summary']}",
        f"② 아직 확인되지 않은 내용: {record['not_verified']}",
        f"③ CK 잠정 대응: {record['ck_candidate'] or '없음'} / {record['ck_mapping_status']}",
    ]
    if rule is None:
        out += [
            "④ CK 기준표 근거: 직접 대응 규칙 없음",
            "⑤ 확인/조치 종류: CK 연결 전이므로 확정하지 않음",
            "⑥ 조치 제안 문장: 생성하지 않음 (기준표 대응·승인 필요)",
        ]
    else:
        out += [
            f"④ CK 기준표 판정 종류: {rule['judgment_type']}",
            f"   확인 항목: {rule['check_item']}",
            f"   자료 한계: {rule['data_limitation']}",
            f"⑤ 확인할 것: {rule['check_required']}",
            f"   기준표 조치 종류: {rule['action_type']}",
            f"   기준표 근거 상태: {rule['evidence_status']}",
            f"   법령 후보(원문 대조 전): {rule.get('legal_reference_candidate') or '없음'}",
            "⑥ 조치 제안 문장: 운영 출력 보류 (CK 판정·문장 승인되지 않음)",
        ]
        if record['ai10_test_scope'] == '적합':
            out.append(
                "   [설명용 조합 예시 · AI 생성/승인 문장 아님] "
                f"민원 기록에는 다음과 같은 주장이 담겨 있습니다: {record['complaint_claim_summary']}. "
                f"해당 장소에서 '{rule['check_required']}'를 확인하고 "
                f"'{rule['action_type']}'의 필요성을 검토할 수 있습니다."
            )
    out += [
        "⑦ 실제 조치/처리결과: 확인되지 않음 (처리일은 조치완료 증거가 아님)",
        "⑧ 실제 후보 적용: 차단 / DB·판정 엔진·운영자 승인 미연결",
    ]
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="실제 민원 16건 근거 추적 보기")
    parser.add_argument("--id", default="SAMPLE-01", help="SAMPLE-01 등 샘플 ID")
    parser.add_argument("--all", action="store_true", help="16건 전체")
    args = parser.parse_args()
    records = json.loads(SAMPLES.read_text(encoding="utf-8-sig"))["records"]
    rules = {r["rule_id"]: r for r in json.loads(RULES.read_text(encoding="utf-8-sig"))["rules"]}
    chosen = records if args.all else [r for r in records if r["sample_id"] == args.id]
    if not chosen:
        parser.error(f"샘플 ID 없음: {args.id}")
    for idx, record in enumerate(chosen):
        if idx:
            print("\n" + "-" * 65 + "\n")
        print(preview(record, rules.get(record["ck_candidate"])))
    print("\n※ 입력 JSON 읽기 전용. AI 호출·DB 접근·저장 없음. 미승인 예시를 운영 판단에 사용 금지.")


if __name__ == "__main__":
    main()
