import sys
from pathlib import Path

# public_api 폴더 위치 찾기
PUBLIC_API = Path(__file__).resolve().parents[1]

# Python이 해당 폴더에서도 파일을 찾도록 설정
if str(PUBLIC_API) not in sys.path:
    sys.path.insert(0, str(PUBLIC_API))
