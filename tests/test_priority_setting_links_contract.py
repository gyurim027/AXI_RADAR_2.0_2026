"""설정 연결 시험을 별도 Python에서 실행해 다른 시험의 app 모듈을 보존한다."""
from pathlib import Path
import os
import subprocess
import sys
import unittest

class PrioritySettingLinksContractTests(unittest.TestCase):
    def test_isolated_contract_suite(self):
        root=Path(__file__).resolve().parents[1]
        suite=root/'tests/priority_setting_links_contract/contract_suite.py'
        env=dict(os.environ,RADAR_LINK_TEST_ROOT=str(root),PYTHONUTF8='1')
        result=subprocess.run([sys.executable,str(suite),'-q'],cwd=str(root),env=env,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
        output=(result.stdout+result.stderr).decode('utf-8','replace')
        self.assertEqual(result.returncode,0,output)
        self.assertIn('Ran 45 tests',output)

if __name__=='__main__':unittest.main()
