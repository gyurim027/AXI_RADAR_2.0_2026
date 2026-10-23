"""민원 샘플 → CK 잠정 연결 → CK 유형별 Gemini 초안 (DB 없이 시험).

배치 위치: radar-ai10-action/tests/test_ai10_complaint_gemini_bridge.py
명령:
  uv run python tests/test_ai10_complaint_gemini_bridge.py --id SAMPLE-01
  uv run python tests/test_ai10_complaint_gemini_bridge.py --all
  uv run python tests/test_ai10_complaint_gemini_bridge.py --all --generate

주의: --generate를 넣을 때만 Gemini API 호출. 동일 CK는 실행당 한 번만 호출.
민원 원문/샘플 내용은 Gemini로 보내지 않음.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SAMPLES = DATA / "RADAR_AI10_민원샘플_정리_v1.json"
RULES = DATA / "ai10_ck_rules_v0.4.json"


def read_json(path):
    if not path.is_file():
        raise FileNotFoundError(f"필수 파일 없음: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def make_result(record, rule):
    candidate = record.get("ck_candidate")
    matched = bool(rule)
    # 샘플은 운영 CK 확정 자료가 아니므로 대응 가능성만 표시한다.
    return {
        "sample_id": record["sample_id"],
        "source_row_number": record["source_row_number"],
        "title": record["sanitized_title"],
        "complaint_claim": record["complaint_claim_summary"],
        "claim_verification": record["fact_status"],
        "not_verified": record["not_verified"],
        "test_scope": record["ai10_test_scope"],
        "ck_candidate": candidate,
        "ck_link_status": record["ck_mapping_status"],
        "ck_rule": {
            "judgment_type": rule["judgment_type"],
            "check_item": rule["check_item"],
            "data_limitation": rule["data_limitation"],
            "check_required": rule["check_required"],
            "action_type": rule["action_type"],
            "evidence_status": rule["evidence_status"],
            "legal_reference_candidate_unverified": rule.get("legal_reference_candidate"),
        } if matched else None,
        "ck_judgment_confirmed": False,
        "approval_status": "미승인",
        "final_candidate_proposal": None,
        "draft_generation": "CK 후보 없음" if not matched else "Gemini 실행 전",
    }


def main():
    parser = argparse.ArgumentParser()
    select = parser.add_mutually_exclusive_group()
    select.add_argument("--id", default=None, help="SAMPLE-01 등")
    select.add_argument("--all", action="store_true", help="16건 전체")
    parser.add_argument("--generate", action="store_true",
                        help="실제 Gemini API 호출: CK 유형당 한 번만 생성")
    parser.add_argument("--save", type=Path, help="결과 JSON 저장 경로(선택)")
    args = parser.parse_args()

    records = read_json(SAMPLES)["records"]
    rules = {r["rule_id"]: r for r in read_json(RULES)["rules"]}
    chosen = records if args.all else [
        r for r in records if r["sample_id"] == (args.id or "SAMPLE-01")
    ]
    if not chosen:
        parser.error("해당 SAMPLE ID가 없습니다.")
    outputs = [make_result(r, rules.get(r.get("ck_candidate"))) for r in chosen]

    if args.generate:
        # 기존 AI-10 생성 함수를 그대로 사용한다: 기준표만 Gemini에 전달한다.
        sys.path.insert(0, str(ROOT))
        from app.services.ai10_draft import generate_draft
        cache = {}
        for out in outputs:
            ck = out["ck_candidate"]
            if out["ck_rule"] is None:
                continue
            if ck not in cache:
                try:
                    draft = generate_draft(ck)
                    cache[ck] = {"draft_template": draft.draft_template,
                                 "review_note": draft.review_note,
                                 "status": "생성됨 (미승인)"}
                except Exception as exc:
                    cache[ck] = {"status": "생성 실패",
                                 "error": f"{type(exc).__name__}: {exc}"}
            out["draft_generation"] = cache[ck]
    else:
        for out in outputs:
            if out["ck_rule"]:
                out["draft_generation"] = "연결 확인만 수행 (--generate 입력 시 CK별 Gemini 호출)"

    for out in outputs:
        print("=" * 65)
        print(f"{out['sample_id']} | 원본 {out['source_row_number']} | {out['title']}")
        print(f"[신고인의 주장] {out['complaint_claim']}")
        print(f"[사실 확인] {out['claim_verification']}")
        print(f"[미확인] {out['not_verified']}")
        print(f"[연결] {out['ck_candidate'] or '없음'} / {out['ck_link_status']}")
        rule = out["ck_rule"]
        if rule:
            print(f"[CK 판정 기준] {rule['judgment_type']}")
            print(f"[CK 자료 한계] {rule['data_limitation']}")
            print(f"[CK 확인 사항] {rule['check_required']}")
            print(f"[CK 조치 종류] {rule['action_type']}")
            print(f"[법령 근거 후보/검증 전] {rule['legal_reference_candidate_unverified']}")
        else:
            print("[CK 기준] 연결 대상 없음. 임의 생성 차단")
        generation = out["draft_generation"]
        if isinstance(generation, dict):
            print(f"[Gemini] {generation['status']}")
            if generation.get("draft_template"):
                print(f"[CK 유형별 초안] {generation['draft_template']}")
                print(f"[운영자 확인 메모] {generation['review_note']}")
            elif generation.get("error"):
                print(f"[호출 오류] {generation['error']}")
        else:
            print(f"[Gemini] {generation}")
        print("[최종 후보 조치 제안] 없음 / CK 확정·운영자 승인·대상 값 연결 전")
    print("=" * 65)
    print("이 시험은 실제 민원→CK 잠정 연결→CK별 Gemini 생성 흐름이다.")
    print("개별 민원 내용은 Gemini에 보내지 않으며 운영 최종 문장도 생성하지 않는다.")
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(outputs, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"결과 저장: {args.save}")


if __name__ == "__main__":
    main()
