from pathlib import Path
from html import escape
from app.core import db

def show(value):
    return escape("미확인" if value is None else str(value))

rows = db.read_only("""
    SELECT upload_id,
           자료_이름 AS name,
           출처 AS source,
           기준일 AS basis_date,
           올린_시각 AS uploaded_at,
           검사_결과 AS check_result,
           행_수 AS row_count
    FROM mysqlteam02db.data_upload
    ORDER BY upload_id
""")

fields = [
    ("upload_id", "접수 번호"),
    ("name", "자료 이름"),
    ("source", "출처"),
    ("basis_date", "자료 기준일"),
    ("uploaded_at", "접수 시각"),
    ("check_result", "기록된 검사 결과"),
    ("row_count", "기록된 행 수"),
]
header = "".join("<th>" + label + "</th>" for _, label in fields)
body = "".join(
    "<tr>" + "".join("<td>" + show(row[key]) + "</td>" for key, _ in fields)
    + "<td>미확인</td></tr>"
    for row in rows
)

page = """<!doctype html><html lang="ko"><meta charset="utf-8">
<title>A-01 실제 DB 자료 목록</title>
<style>
body{font-family:"Malgun Gothic",sans-serif;margin:30px;line-height:1.7}
table{border-collapse:collapse}th,td{border:1px solid #ccc;padding:10px}
th{background:#edf2f7}.scroll{overflow-x:auto}
</style>
<h1>A-01 실제 DB 자료 접수 목록</h1>
<p>팀 DB의 접수 기록을 조회한 결과입니다.</p>
<p>갱신 주기가 확인되지 않아 최신 여부는 판단하지 않았습니다.
접수 시각은 원본 수집일과 다를 수 있습니다.</p>
<p>행 수와 검사 결과는 접수 기록의 값이며, 이번 실행에서 재검사한 결과가 아닙니다.</p>
<div class="scroll"><table><tr>"""
page += header + "<th>최신 여부</th></tr>" + body + "</table></div></html>"

output = Path("outputs/a01_db/catalog.html")
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(page, encoding="utf-8")
print("실제 DB 접수 기록:", len(rows), "개")
print("저장 위치:", output.resolve())
