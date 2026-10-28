"""SE-02 C-07 content-verified whole-result reuse (no DB access or writes).

Deliberately does NOT merge monthly aggregate counts. Cross-month repeat/dedup
semantics require a full builder whenever any source or rule input changes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Mapping
import hashlib
import json
import os
import tempfile
import time

SCHEMA = 'se02-c07-whole-v1'


class CacheBlocked(ValueError):
    pass


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _canonical_bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


@dataclass(frozen=True)
class Context:
    start: str
    end: str
    source_files: tuple[str, ...]
    classification_version: str
    spatial_version: str
    repeat_dedup_version: str
    location_quality_version: str
    algorithm_version: str
    # Put further decision-driving flags in this mapping, not just prose notes.
    extra_rules: Mapping[str, str] | None = None

    def validate(self) -> None:
        try:
            a, b = date.fromisoformat(self.start), date.fromisoformat(self.end)
        except ValueError as exc:
            raise CacheBlocked('invalid date') from exc
        if a > b or not self.source_files or len(self.source_files) != len(set(self.source_files)):
            raise CacheBlocked('invalid period or sources')
        values = (self.classification_version, self.spatial_version,
                  self.repeat_dedup_version, self.location_quality_version, self.algorithm_version)
        if any(not isinstance(x, str) or not x.strip() for x in values):
            raise CacheBlocked('missing version identity')
        if self.extra_rules is not None and any(
            not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip()
            for k, v in self.extra_rules.items()
        ):
            raise CacheBlocked('invalid rule metadata')


def identity(ctx: Context) -> tuple[str, dict]:
    ctx.validate()
    files = []
    for path in sorted(ctx.source_files):
        p = Path(path).resolve(strict=True)
        if not p.is_file():
            raise CacheBlocked(f'not a file: {p}')
        before = p.stat()
        digest = sha256_file(p)
        after = p.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise CacheBlocked(f'source changed during hashing: {p}')
        files.append({'path': str(p), 'sha256': digest, 'bytes': after.st_size})
    manifest = {'schema': SCHEMA, 'start': ctx.start, 'end': ctx.end,
                'sources': files, 'classification_version': ctx.classification_version,
                'spatial_version': ctx.spatial_version,
                'repeat_dedup_version': ctx.repeat_dedup_version,
                'location_quality_version': ctx.location_quality_version,
                'algorithm_version': ctx.algorithm_version,
                'extra_rules': dict(ctx.extra_rules or {})}
    return hashlib.sha256(_canonical_bytes(manifest)).hexdigest(), manifest


def _atomic_write(dest: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(prefix='.se02-', suffix='.tmp', dir=dest.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def use_or_rebuild(ctx: Context, cache_dir: str | Path,
                   build: Callable[[], bytes]) -> dict:
    """Return verified CSV path; `build` runs only on cache miss.

    `build` should run the *existing complete C-07 pipeline* and return its CSV
    bytes. This function does not approve inputs for official 77/78 writes.
    Designed for one writer per cache directory; external lock required for
    concurrent writers or workers. Never use an unverified legacy CSV as cache.
    """
    t0 = time.perf_counter()
    key, manifest = identity(ctx)
    directory = Path(cache_dir)
    directory.mkdir(parents=True, exist_ok=True)
    csv_path, meta_path = directory / f'{key}.csv', directory / f'{key}.json'
    if csv_path.is_file() and meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            if (meta.get('identity') == key and meta.get('inputs') == manifest
                and meta.get('output_sha256') == sha256_file(csv_path)
                and meta.get('output_bytes') == csv_path.stat().st_size):
                return {'reused': True, 'identity': key, 'csv': str(csv_path),
                        'duration_seconds': time.perf_counter() - t0}
        except (ValueError, OSError, TypeError, KeyError):
            pass
    payload = build()
    if not isinstance(payload, bytes) or not payload:
        raise CacheBlocked('builder must return nonempty CSV bytes')
    # Fail closed if inputs changed while long-running build was running.
    new_key, newer = identity(ctx)
    if new_key != key or newer != manifest:
        raise CacheBlocked('inputs changed during full aggregation')
    output_digest = hashlib.sha256(payload).hexdigest()
    record = {'identity': key, 'inputs': manifest,
              'output_sha256': output_digest, 'output_bytes': len(payload)}
    _atomic_write(csv_path, payload)
    _atomic_write(meta_path, _canonical_bytes(record))
    return {'reused': False, 'identity': key, 'csv': str(csv_path),
            'duration_seconds': time.perf_counter() - t0}
