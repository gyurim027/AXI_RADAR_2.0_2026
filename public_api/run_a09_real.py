"""A-09 실제 자료 시점 표시. PUBLIC_REAL 폴더에서 실행.
python run_a09_real.py --test : 가상 경계값 검사만
python run_a09_real.py : 기존 9종 실제 파일을 재확인하고 자료 시점 표 생성
DB·네트워크·LLM 호출 없음. 입력 파일 수정 없음.
"""
import argparse
import json
import re
import sys
import unittest
from datetime import date, datetime, timezone, timedelta
from html import escape
from pathlib import Path

ONE_OFF = {'DAT-23','DAT-24','DAT-25','DAT-26','DAT-27','DAT-28'}


def describe(data_id, evidence):
    if evidence is None:
        return dict(label='자료 기준일 미확인', period=None, precision=None,
                    historical=False, reason='이번 실제 파일 연결에서 확인하지 않음',latest_status='판정 보류')
    values = evidence.get('basis')
    if not isinstance(values,list) or not values:
        return dict(label='자료 기준일 미확인', period=None, precision=None,
                    historical=False,reason='입력에 기준일·연도 없음',latest_status='판정 보류')
    precision=evidence.get('basis_precision')
    normalized=[]
    for value in values:
        if not isinstance(value,str):
            raise ValueError('invalid_basis_type')
        if precision=='일':
            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',value) or date.fromisoformat(value).isoformat()!=value:
                raise ValueError('invalid_date')
        elif precision=='연도':
            if not re.fullmatch(r'[0-9]{4}',value) or not 1000<=int(value)<=9999:
                raise ValueError('invalid_year')
        else:
            raise ValueError('basis_precision_required')
        normalized.append(value)
    normalized=sorted(set(normalized))
    years=sorted(set(v[:4] for v in normalized))
    period=normalized[0] if len(normalized)==1 else normalized[0]+' ~ '+normalized[-1]
    label=(years[0]+'년 자료') if len(years)==1 else (years[0]+'~'+years[-1]+'년 자료')
    historical=data_id in ONE_OFF
    if historical:label+=' · 과거 기록'
    return dict(label=label,period=period,precision=precision,historical=historical,
                reason='기획·관리 대장 v0.4.2에서 1회성 조사로 분류된 6종' if historical else '기준일의 연도만으로 최신 여부를 판단하지 않음',
                latest_status='판정 보류')


def build(catalog):
    items=[]
    for item in catalog['items']:
        evidence=item.get('verified_evidence')
        row=dict(data_id=item['data_id'],name=item['name'],**describe(item['data_id'],evidence))
        row['basis_values']=evidence.get('basis',[]) if evidence else []
        row['evidence_kind']=evidence.get('kind') if evidence else None
        row['original_status']=evidence.get('original_status') if evidence else '미확인'
        row['received_at']=evidence.get('received_at') if evidence else None
        items.append(row)
    return dict(checked_at=datetime.now(timezone(timedelta(hours=9))).isoformat(),
                items=items,known_count=sum(r['period'] is not None for r in items),
                historical_count=sum(r['historical'] for r in items),
                unknown_count=sum(r['period'] is None for r in items),db_written=False,
                actual_source='기존 A-01 실제 파일 연결 9종을 다시 검증한 결과',
                note='수집일·접수일을 자료 기준일로 대신 쓰지 않음. 보고서·실제 화면 연결은 별도.')


def render(report):
    def t(v):return escape('미확인' if v is None else str(v))
    heads=['DAT 번호','자료','화면용 시점 표시','실제 날짜·연도 범위','날짜 정밀도','원본 상태','최신 여부']
    rows=[]
    for r in report['items']:
        values=[r['data_id'],r['name'],r['label'],r['period'],r['precision'],r['original_status'],r['latest_status']]
        rows.append('<tr'+(' class="history"' if r['historical'] else '')+'>'+''.join('<td>'+t(v)+'</td>' for v in values)+'</tr>')
    return '''<!doctype html><html lang="ko"><meta charset="utf-8"><title>A-09 실제 자료 시점</title>
<style>body{font-family:'Malgun Gothic',sans-serif;margin:28px;color:#17263c;line-height:1.7}h1{font-size:26px}.notice{padding:16px;background:#fff3d6}.summary{padding:16px;background:#eaf5ef;margin:18px 0}.scroll{overflow:auto;max-height:72vh}table{border-collapse:collapse;font-size:14px}th,td{padding:10px;border:1px solid #ccd4df;min-width:105px;vertical-align:top}th{position:sticky;top:0;background:#e9eff7}td:nth-child(2){min-width:220px}.history{background:#fff6e4}</style>
<h1>A-09 실제 자료 시점 표시</h1><div class="summary">기준일·연도 확인 '''+t(report['known_count'])+'종 / 일회성 조사 과거 기록 '+t(report['historical_count'])+'종 / 이번 연결에서 시점 미확인 '+t(report['unknown_count'])+'''종</div>
<div class="notice">2022년 일회성 조사 6종에만 ‘과거 기록’을 표시합니다. 오래된 연도라는 이유만으로 모든 자료를 과거 기록으로 분류하지 않습니다. ‘미확인’은 미수집이나 0건이 아닙니다. API 수집일·CSV 접수일과 자료 기준일을 구분합니다. 최신 여부·팀 승인·실제 보고서 및 화면 연결은 아직 확정하지 않았습니다.</div><p>노란 행: 일회성 현장조사 자료. 연도 단위인 사고 자료에 임의 월·일을 추가하지 않습니다.</p>
<div class="scroll"><table><tr>'''+''.join('<th>'+t(h)+'</th>' for h in heads)+'</tr>'+''.join(rows)+'</table></div><p>확인 시각: '+t(report['checked_at'])+'</p><p>DB·원문 수정·새 수집·LLM 호출 없음.</p></html>'


class DateLabelTests(unittest.TestCase):
    def test_oneoff_historical(self):
        r=describe('DAT-23',{'basis':['2022-09-19','2022-10-07'],'basis_precision':'일'})
        self.assertEqual(r['label'],'2022년 자료 · 과거 기록')
        self.assertEqual(r['period'],'2022-09-19 ~ 2022-10-07')
    def test_year_range_no_invented_day(self):
        r=describe('DAT-01',{'basis':['2019','2025'],'basis_precision':'연도'})
        self.assertEqual(r['label'],'2019~2025년 자료');self.assertFalse(r['historical'])
        self.assertEqual(r['period'],'2019 ~ 2025')
    def test_api_not_latest(self):
        r=describe('DAT-06',{'basis':['2026-05-12'],'basis_precision':'일'})
        self.assertEqual(r['label'],'2026년 자료');self.assertEqual(r['latest_status'],'판정 보류')
    def test_unknown_not_zero(self):
        self.assertEqual(describe('DAT-03',None)['label'],'자료 기준일 미확인')
    def test_receipt_date_not_substituted(self):
        r=describe('DAT-23',{'basis':[],'basis_precision':'일','received_at':'2026-10-23'})
        self.assertIsNone(r['period']);self.assertFalse(r['historical'])
    def test_invalid_date_blocked(self):
        with self.assertRaises(ValueError):describe('DAT-06',{'basis':['2026-02-30'],'basis_precision':'일'})
    def test_precision_required(self):
        with self.assertRaises(ValueError):describe('DAT-02',{'basis':['2021']})
    def test_html_escaped(self):
        r=build({'items':[{'data_id':'DAT-03','name':'<script>','verified_evidence':None}]})
        self.assertNotIn('<script>',render(r));self.assertIn('&lt;script&gt;',render(r))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--test',action='store_true')
    args=parser.parse_args()
    if args.test:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(DateLabelTests)
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
    public=Path(__file__).resolve().parent
    common=public.parent if (public.parent/'run_a01_all.py').is_file() else public.parents[1]/'I07_LLM_TEST/AXI_RADAR_2.0_2026-feature-w05-llm'
    sys.path.insert(0,str(common))
    from run_a01_all import connect
    catalog=connect(common,'r_1023_021317_a4b8d0')
    report=build(catalog)
    output=public/'outputs/a09_real'
    output.mkdir(parents=True,exist_ok=True)
    (output/'data_dates.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'data_dates.html').write_text(render(report),encoding='utf-8')
    print('실제 자료 시점 확인:',report['known_count'],'종 / 과거 기록:',report['historical_count'],'종')
    for r in report['items']:
        if r['period'] is not None:print(r['data_id'],r['label'],'/',r['period'])
    print('화면:',output/'data_dates.html')
    print('실제 보고서·팀 화면 연결, 최신 여부 판정은 아직 하지 않았습니다.')
    return 0


if __name__=='__main__':
    sys.exit(main())
