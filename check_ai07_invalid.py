import json
import urllib.request
import urllib.error

payload = {
    "official_use": False,
    "run_id": "SYNTHETIC-RUN-A",
    "gid": "SYNTHETIC-GRID-A",
    "score": None,
    "rank_no": None,
    "domain_scores": None,
    "indicator_contributions": None,
    "observation": {
        "indicator": "COND_적치물_수",
        "state": "OBSERVED_ZERO",
        "value": "7"
    }
}
request = urllib.request.Request(
    "http://127.0.0.1:8000/api/ai07/development/unevaluated-explanation",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(request, timeout=10) as response:
        print("HTTP:", response.status)
        print("확인 필요: 잘못된 입력을 받아들였습니다.")
except urllib.error.HTTPError as error:
    print("HTTP:", error.code)
    print(error.read().decode("utf-8"))
