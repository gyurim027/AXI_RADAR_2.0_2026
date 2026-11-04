"""서버를 켠 뒤 uv run python scripts/ai07_server_smoke.py 로 실행."""
import json
from pathlib import Path
from urllib.request import Request, urlopen
ROOT=Path(__file__).resolve().parents[1]
cards=json.loads((ROOT/'samples/cards.json').read_text(encoding='utf-8'))
card=cards[0]['card'] if isinstance(cards,list) else next(iter(cards.values()))
checks=[('explanation',card),('refine',{'card':card}),('request',json.loads((ROOT/'samples/request.json').read_text(encoding='utf-8'))),('report',json.loads((ROOT/'samples/report.json').read_text(encoding='utf-8')))]
for name,payload in checks:
 req=Request('http://127.0.0.1:8000/api/ai07/synthetic/'+name,data=json.dumps(payload,ensure_ascii=False).encode('utf-8'),headers={'Content-Type':'application/json'},method='POST')
 with urlopen(req,timeout=30) as response:
  result=json.loads(response.read().decode('utf-8'))
  print(name+': HTTP '+str(response.status))
print('가상 자료 서버 연결 확인 완료. 실제 AI·DB 연결 시험은 아닙니다.')
