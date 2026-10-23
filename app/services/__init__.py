"""Locate existing feature modules without moving or duplicating their files."""
from pathlib import Path

_services_dir = Path(__file__).resolve().parent
for _feature_dir in ("AI-10", "D-10", "F-01,03,04", "G-01~06"):
    __path__.append(str(_services_dir / _feature_dir))
