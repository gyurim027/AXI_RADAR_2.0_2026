import json
import sys
from decimal import Decimal

def explain(item):
    if item.get("official_use") is not False:
        raise ValueError("이 시험은 공식 사용이 아닌 예시만 처리합니다.")
    for key in ("score", "rank_no", "domain_scores", "indicator_contributions"):
        if key not in item or item[key] is not None:
            raise ValueError("이 시험은 점수·순위·기여점이 없는 경우만 처리합니다.")

    observation = item.get("observation", {})
    if observation.get("indicator") != "COND_적치물_수":
        raise ValueError("예상한 적치물 관측 항목이 아닙니다.")

    state = observation.get("state")
    value = observation.get("value")

    if state == "NOT_SURVEYED":
        if value is not None:
            raise ValueError("미조사 상태인데 관측값이 들어 있습니다.")
        observation_text = "적치물은 미조사 상태이므로 관측 건수를 알 수 없습니다."
    elif state in ("OBSERVED_ZERO", "OBSERVED_VALUE"):
        if value is None or isinstance(value, bool):
            raise ValueError("관측값이 올바르지 않습니다.")
        count = Decimal(str(value))
        if not count.is_finite() or count < 0 or count != count.to_integral_value():
            raise ValueError("관측 건수는 0 이상의 정수여야 합니다.")
        if state == "OBSERVED_ZERO" and count != 0:
            raise ValueError("관측 0건 상태와 숫자가 다릅니다.")
        if state == "OBSERVED_VALUE" and count <= 0:
            raise ValueError("양수 관측 상태와 숫자가 다릅니다.")
        observation_text = f"제공된 적치물 관측 건수는 {int(count)}건입니다."
    else:
        raise ValueError("확인하지 못한 관측 상태입니다.")

    return (
        "[진규님 제공 개발용 예시 / 공식 산정 결과 아님]\n"
        f"회차: {item['run_id']}\n"
        f"격자: {item['gid']}\n"
        "공식 점수와 순위가 제공되지 않아 표시하지 않았습니다.\n"
        "분야별 점수와 지표별 기여점도 제공되지 않았습니다.\n"
        + observation_text + "\n"
        "이 관측 정보만으로 안전 여부를 판단하지 않습니다.\n"
        "민원의 점수 반영 여부는 이 입력만으로 확인할 수 없습니다."
    )

if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8-sig") as file:
        items = json.load(file)
    if not isinstance(items, list) or not items:
        raise ValueError("비어 있지 않은 예시 목록이 필요합니다.")
    results = [explain(item) for item in items]
    for index, text in enumerate(results, 1):
        print(f"\n--- 예시 {index} ---")
        print(text)
    print(f"\n예시 {len(results)}건 설명 완료. 실제 LLM·API 연결 시험은 아닙니다.")
