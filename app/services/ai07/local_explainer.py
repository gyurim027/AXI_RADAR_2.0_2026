def explain_candidate(candidate):
    """변환된 후보 한 건을 받아 내부 문장 틀로 설명합니다."""

    parts = [
        f"{name} {value}점"
        for name, value in candidate["contributions"].items()
    ]

    text = (
        f"{candidate['place']} 격자 {candidate['candidate_id']}의 "
        f"승인 전 시험 점수는 {candidate['score']}점이며, "
        f"전체 {candidate['total']:,}개 격자 중 "
        f"입력된 시험 순위는 {candidate['rank']}위입니다. "
        f"항목별 점수 기여는 {', '.join(parts)}입니다. "
    )

    if candidate["complaint_included"] is False:
        text += (
            "민원은 점수에 반영되지 않았으며, "
            "민원 0건을 의미하지 않습니다. "
        )

    text += (
        f"산식 버전은 {candidate['formula_version']}입니다. "
        "공식 위험도 평가가 아닙니다. "
        "지표별 원자료 출처와 기준일은 이 입력에 없어 "
        "추가 확인이 필요합니다. "
        "이번 설명 생성에서는 원자료 전체를 재검산하지 않았습니다."
    )

    return {
        "candidate_id": candidate["candidate_id"],
        "rank_test": candidate["rank"],
        "score_test": candidate["score"],
        "generation_method": "local_template",
        "external_api_called": False,
        "explanation": text,
    }

# 아래는 2026-10-20 화면 연결을 위해 추가한 함수입니다.
# 위 explain_candidate 함수는 업로드된 원래 코드를 그대로 보존했습니다.
# 화면에는 기여점수/전체 격자 수/산식 버전이 없으므로 추정하지 않습니다.
def explain_frontend_candidate(facts):
    """검증한 프론트엔드 mock 입력으로 설명을 만듭니다. 파일/외부 API 접근 없음."""
    def display_number(value):
        return str(int(value)) if float(value).is_integer() else str(value)

    score = display_number(facts["score"])
    text = (
        f"[가상 연결 시험] {facts['runName']} 회차의 격자 {facts['gid']}는 "
        f"{score}점이며, 현재 조회 범위의 순위는 {facts['rank']}위입니다. "
    )
    parts = []
    for evidence in facts["evidence"]:
        value = evidence["value"] if evidence["value"] is not None else "확인할 수 없음"
        year = evidence["basisYear"] if evidence["basisYear"] is not None else "미제공"
        source = evidence["source"] or "미제공"
        parts.append(f"{evidence['item']}: {value} (기준연도: {year}, 출처: {source}).")
    text += " ".join(parts) if parts else "항목별 근거 자료가 제공되지 않았습니다."
    text += (
        " 항목별 점수 기여는 이 화면 입력에 제공되지 않아 설명하지 않았습니다."
        " 민원의 점수 반영 여부는 확인할 수 없습니다."
        " 민원 자료 유무는 민원 0건 또는 안전함을 의미하지 않습니다."
        " 이 설명은 화면 연결을 위한 가상 시험이며 공식 위험도 평가가 아닙니다."
    )
    return {
        "candidate_id": facts["gid"],
        "run_id": facts["runId"],
        "rank_test": facts["rank"],
        "score_test": facts["score"],
        "generation_method": "local_template",
        "external_api_called": False,
        "python_function": "explain_frontend_candidate",
        "explanation": text,
    }
