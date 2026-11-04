"""D-10 operational DB77 round creation; no schema mutation, no memory IDs.

This service needs schema v2.4 (three setting FK columns) and existing D-10
approval / authentication at its caller. It never opens review state.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date

SETTING_FIELDS = ('weight_setting_version_id', 'threshold_setting_version_id',
                  'priority_condition_setting_version_id')
LOCK_NAME = 'RADAR:D10:PRIORITY_RUN_ID_ALLOC_V1'

class D10RunBlocked(ValueError):
    pass

@dataclass(frozen=True)
class RunCreation:
    build_id: str
    rule_version: str
    period_start: date
    period_end: date
    weight_setting_version_id: int
    threshold_setting_version_id: int
    priority_condition_setting_version_id: int
    note: str = 'D10_CREATED_AWAITING_SCORING'


def _one(cur):
    rows = cur.fetchall()
    if len(rows) != 1:
        raise D10RunBlocked('UNEXPECTED_DB_RESULT')
    return rows[0]


def create_d10_run(request: RunCreation, *, explicit_creation_approval: bool = False,
                   connection_factory=None, source_audit=None) -> dict:
    """Create one durable D-10 run, serializing cooperative allocation.

    This does NOT authorize scoring/writing or open the run for review.
    GET_LOCK is connection-scoped; explicit RELEASE_LOCK is mandatory.
    """
    if explicit_creation_approval is not True:
        raise D10RunBlocked('EXPLICIT_D10_CREATION_APPROVAL_REQUIRED')
    if not isinstance(request, RunCreation):
        raise D10RunBlocked('INVALID_REQUEST')
    if any(not isinstance(x, str) or not x.strip() for x in (request.build_id, request.rule_version)):
        raise D10RunBlocked('BUILD_AND_POLICY_REQUIRED')
    if len(request.build_id) > 30 or len(request.rule_version) > 255:
        raise D10RunBlocked('BUILD_OR_RULE_TOO_LONG')
    if not isinstance(request.period_start, date) or not isinstance(request.period_end, date) or request.period_start > request.period_end:
        raise D10RunBlocked('INVALID_PERIOD')
    ids = tuple(getattr(request, f) for f in SETTING_FIELDS)
    if any(type(v) is not int or v <= 1 or v > 9223372036854775807 for v in ids) or len(set(ids)) != 3:
        raise D10RunBlocked('THREE_DISTINCT_NON_DEMO_SETTINGS_REQUIRED')
    if not isinstance(request.note, str) or len(request.note) > 100:
        raise D10RunBlocked('NOTE_TOO_LONG')
    note = request.note
    if source_audit is not None:
        from app.services.scoring.source_audit_lineage import revalidate_source_audit, source_audit_note
        checked = revalidate_source_audit(source_audit, start=request.period_start, end=request.period_end)
        if note != 'D10_CREATED_AWAITING_SCORING':
            raise D10RunBlocked('SOURCE_AUDIT_NOTE_ALREADY_USED')
        note = source_audit_note(checked.audit_sha256)
    if connection_factory is None:
        from app.core.db import raw_connection
        connection_factory = raw_connection
    con = connection_factory()
    locked = False
    try:
        with con.cursor() as cur:
            native_mode = request.build_id.startswith('db59:')
            if native_mode:
                from app.services.scoring.input_builds import _begin
                _begin(cur)
            cur.execute('SELECT GET_LOCK(%s, %s) AS acquired', (LOCK_NAME, 5))
            if _one(cur).get('acquired') != 1:
                raise D10RunBlocked('RUN_ID_ALLOCATOR_LOCK_UNAVAILABLE')
            locked = True
            # Fail closed until the existing DB62/77 schema deployment is complete.
            cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='priority_run'")
            cols = {row['COLUMN_NAME'] for row in cur.fetchall()}
            required = {'run_id','build_id','rule_version','created_at','note','period_start','period_end',*SETTING_FIELDS}
            if not required.issubset(cols):
                raise D10RunBlocked('DB77_V24_SCHEMA_NOT_DEPLOYED')
            cur.execute("SELECT EXTRA FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='priority_run' AND COLUMN_NAME='run_id'")
            extra = str(_one(cur).get('EXTRA') or '').lower()
            if 'auto_increment' in extra:
                raise D10RunBlocked('DB77_ID_CONTRACT_CHANGED')
            if native_mode:
                from app.services.scoring.native_build_manifest import validate_run_text_capacity, NativeBuildBlocked
                cur.execute("SELECT TABLE_NAME AS table_name,COLUMN_NAME AS column_name,COLUMN_TYPE AS column_type FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='priority_run'")
                try:
                    validate_run_text_capacity(list(cur.fetchall()),build_id=request.build_id,
                        rule_version=request.rule_version,note='r03:'+'0'*64)
                except NativeBuildBlocked as exc:
                    raise D10RunBlocked(str(exc)) from exc
                # Same lock order as registration/review/writer: DB59 row, then settings.
                from app.services.scoring.input_builds import _stored
                try: _stored(cur,int(request.build_id[5:]))
                except ValueError as exc: raise D10RunBlocked('NATIVE_BUILD_NOT_READY:'+str(exc)) from exc
            # Require all 3 settings actually approved. Do not synthesize approvals.
            from app.services.scoring.setting_links import (
                KINDS, _validated_row, validate_references, SettingLinksBlocked
            )
            checked_refs = []
            for sid, expected_kind in zip(ids, KINDS):
                cur.execute(
                    'SELECT setting_version_id,setting_kind,content_ref,'
                    'version_label,NULL AS version_no,approval_status,approved_at '
                    'FROM setting_version WHERE setting_version_id=%s FOR UPDATE',
                    (sid,)
                )
                entry = _one(cur)
                try:
                    checked_refs.append(_validated_row(entry, expected_kind))
                except SettingLinksBlocked as exc:
                    raise D10RunBlocked(str(exc)) from exc
            try:
                validate_references(tuple(checked_refs))
            except SettingLinksBlocked as exc:
                raise D10RunBlocked(str(exc)) from exc
            if native_mode:
                from app.services.scoring.input_builds import verify_execution_build, BuildBlocked
                try:
                    build = verify_execution_build(cur,build_id=request.build_id,
                        policy_sha256=checked_refs[0].content_ref.removeprefix('sha256:'),
                        setting_ids=ids,start=request.period_start,end=request.period_end)
                except (ValueError, KeyError) as exc:
                    raise D10RunBlocked('NATIVE_BUILD_NOT_READY:'+str(exc)) from exc
                checked_audit = build['source_audit']
                if source_audit is not None and source_audit.audit_sha256 != checked_audit.audit_sha256:
                    raise D10RunBlocked('NATIVE_BUILD_AUDIT_ARGUMENT_MISMATCH')
                if request.note != 'D10_CREATED_AWAITING_SCORING':
                    raise D10RunBlocked('NATIVE_BUILD_NOTE_RESERVED')
                from app.services.scoring.source_audit_lineage import source_audit_note
                source_audit = checked_audit
                note = source_audit_note(checked_audit.audit_sha256)
            cur.execute('SELECT COALESCE(MAX(run_id),1)+1 AS next_id FROM priority_run WHERE run_id>1')
            next_id = _one(cur)['next_id']
            if type(next_id) is not int or next_id <= 1 or next_id > 9223372036854775807:
                raise D10RunBlocked('INVALID_NEXT_RUN_ID')
            fields = ('run_id','build_id','rule_version','created_at','note','period_start','period_end',*SETTING_FIELDS)
            vals = (next_id,request.build_id,request.rule_version,note,request.period_start,request.period_end,*ids)
            cur.execute('INSERT INTO priority_run ('+','.join(fields)+') VALUES (%s,%s,%s,CURRENT_TIMESTAMP,%s,%s,%s,%s,%s,%s)', vals)
            cur.execute('SELECT run_id,note FROM priority_run WHERE run_id=%s', (next_id,))
            saved = _one(cur)
            if saved['run_id'] != next_id or saved.get('note') != note:
                raise D10RunBlocked('RUN_INSERT_READBACK_FAILED')
        con.commit()
        return {'run_id': next_id, 'storage': 'DB77', 'creation_status': 'CREATED',
                'scoring_authorized': False, 'review_opened': False,
                'source_audit_sha256': source_audit.audit_sha256 if source_audit is not None else None}
    except Exception:
        con.rollback()
        raise
    finally:
        if locked:
            try:
                with con.cursor() as cur:
                    cur.execute('SELECT RELEASE_LOCK(%s) AS released', (LOCK_NAME,))
            finally:
                con.close()
        else:
            con.close()
