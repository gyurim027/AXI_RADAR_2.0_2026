import unittest
import tempfile
import json
from pathlib import Path
from file_flow import validate,process,digest
from api_collect import collect,parse

P=dict(data_id='DAT-06',name='시험 자료',source='가상 출처',operator='TEST',original_status='가공본',columns=['id','date','count'],key_column='id',date_column='date',decimal_columns=['count'])

class FileTests(unittest.TestCase):
    def test_valid_and_zero(self):
        r=validate(b'id,date,count\n1,2026-10-01,0\n',P)
        self.assertEqual(r['issues'],[]);self.assertEqual(r['total_rows'],1)
    def test_errors_retained(self):
        r=validate(b'id,date,count\n,invalid,x\n2,2026-10-01,1\n2,2026-10-01,1\n',P)
        self.assertEqual(r['total_rows'],3);self.assertEqual(len(r['issues']),5)
    def test_header_fail(self):
        self.assertFalse(validate(b'id,id\n1,1\n',P)['completed'])
    def test_optional_blank_not_zero(self):
        r=validate(b'id,date,count\n1,2026-10-01,\n',P);self.assertEqual(r['issues'],[])
    def test_nonfinite(self):
        r=validate(b'id,date,count\n1,2026-10-01,NaN\n',P);self.assertEqual(r['issues'][0]['code'],'invalid_decimal')
    def test_archive_exact_and_separate(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'a.csv';raw=b'id,date,count\n1,2026-10-01,0\n';p.write_bytes(raw)
            a,r=process(p,P,Path(t)/'out','R1');b,_=process(p,P,Path(t)/'out','R2')
            self.assertNotEqual(a,b);self.assertEqual((a/'received.csv').read_bytes(),raw);self.assertEqual(p.read_bytes(),raw)
            self.assertFalse(r['approved_for_scoring']);self.assertIsNone(r['original_collected_date'])
    def test_complaint_and_path_block(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'a.csv';p.write_bytes(b'id,date,count\n')
            with self.assertRaises(ValueError):process(p,{**P,'data_id':'DAT-64'},Path(t)/'out','R1')
            with self.assertRaises(ValueError):process(p,P,Path(t)/'out','../R1')
            self.assertFalse((Path(t)/'out').exists())

def response(page,total,items):
    return json.dumps({'response':{'header':{'resultCode':'00'},'body':{'pageNo':page,'numOfRows':100,'totalCount':total,'items':items}}}).encode()

class ApiTests(unittest.TestCase):
    def run_api(self,fetch):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        return collect('DAT-06',{'signguNm':'성남시 수정구'},'TEST_KEY',temp.name,fetch=fetch,pause=lambda _:None)
    def test_two_pages(self):
        pages=iter([response(1,101,[{'id':i}for i in range(100)]),response(2,101,[{'id':100}])])
        folder,r=self.run_api(lambda _:next(pages));self.assertTrue(r['complete']);self.assertEqual(r['received_rows'],101)
        self.assertNotIn('TEST_KEY',(folder/'collection.json').read_text(encoding='utf-8'))
    def test_retry_success(self):
        attempts=[]
        def fetch(_):
            attempts.append(1)
            if len(attempts)<2:raise TimeoutError()
            return response(1,1,[{'id':1}])
        _,r=self.run_api(fetch);self.assertTrue(r['complete']);self.assertEqual(len(attempts),2)
    def test_retry_failure(self):
        def fail(_):raise TimeoutError()
        _,r=self.run_api(fail);self.assertFalse(r['complete']);self.assertEqual(r['error_code'],'retry_exhausted')
    def test_partial_not_complete(self):
        _,r=self.run_api(lambda _:response(1,3,[{'id':1}]))
        self.assertFalse(r['complete']);self.assertEqual(r['error_code'],'page_count_mismatch')
    def test_auth_error_not_empty_success(self):
        _,r=self.run_api(lambda _:b'{"response":{"header":{"resultCode":"30"}}}')
        self.assertFalse(r['complete']);self.assertEqual(r['error_code'],'invalid_api_response')
    def test_zero_requires_review(self):
        _,r=self.run_api(lambda _:response(1,0,[]));self.assertTrue(r['complete']);self.assertTrue(r['operator_review_required'])
    def test_duplicates_not_dropped(self):
        _,r=self.run_api(lambda _:response(1,2,[{'id':1},{'id':1}]))
        self.assertFalse(r['complete']);self.assertEqual(r['error_code'],'duplicate_items_review')
    def test_no_key_no_folder(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'out'
            with self.assertRaises(ValueError):collect('DAT-06',{'signguNm':'성남시'},None,p)
            self.assertFalse(p.exists())

if __name__=='__main__':unittest.main()

