"""Locate existing feature modules without moving or duplicating their files."""
from pathlib import Path

_services_dir = Path(__file__).resolve().parent
for _feature_dir in ("ai10", "d10", "f01_f03_f04", "g01_g06"):
    __path__.append(str(_services_dir / _feature_dir))
