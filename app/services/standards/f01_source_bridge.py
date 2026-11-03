"""F-01: read-only source->problem-kind->jurisdiction candidate bridge.

Never manufactures a problem from aggregate scores. Never changes the official
priority run, settings, or department tables.  F-01 '1차 부서 후보' is NOT approval.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Mapping, Iterable
import re

KINDS = ('주정차','적치','조도','가로등','보도','점자블록','파손','단차','신호','횡단보도','점용','보호구역','자전거','노점','공사','육교','지하보도','교통안전시설')
# Explicit reviewable classification mapping; not a claim that all 18 kinds are
# inferable from nine aggregate indicators.
JUR = {
 '주정차': ('JUR-06',), '적치': ('JUR-07',),
 '조도': ('JUR-05',), '가로등': ('JUR-05',),
 '보도': ('JUR-02','JUR-03'), '점자블록': ('JUR-02',),
 '파손': ('JUR-02',), '단차': ('JUR-02',),
 '신호': ('JUR-11',), '횡단보도': ('JUR-01','JUR-23'),
 '점용': ('JUR-07','JUR-08'), '보호구역': ('JUR-01','JUR-10'),
 '자전거': ('JUR-13',), '노점': ('JUR-07',), '공사': ('JUR-08',),
 '육교': ('JUR-16',), '지하보도': ('JUR-16',), '교통안전시설': ('JUR-01','JUR-04')
}
assert len(KINDS)==18 and set(KINDS)==set(JUR)
# Unambiguous incident descriptions. Order important, avoid overly broad tokens.
PATTERNS = [
 ('주정차', r'불법\s*주[·ㆍ\-\s]*정차|불법\s*주차|횡단보도\s*불법\s*주'),
 ('점자블록', r'점자\s*블록\s*(파손|훼손|불량|정비|보수|민원)'),
 ('가로등', r'(가로등|보안등)\s*(고장|불량|소등|미점등|파손|수리|정비)'),
 ('신호', r'(보행\s*신호|신호등)\s*(고장|불량|미작동|수리|정비|시간\s*부족)'),
 ('노점', r'불법\s*노점|노점상\s*(단속|철거|신고)'),
 ('적치', r'노상\s*적치물|불법\s*적치|적치물\s*(제거|단속|신고)|보도\s*적치'),
 ('점용', r'무단\s*점용|불법\s*점용'),
 ('공사', r'공사\s*(중|현장|자재).*?(보행|통행)\s*(차단|방해|불편)|보행로\s*공사\s*차단'),
 ('파손', r'포트홀|도로\s*파임|도로\s*파손'),
 ('단차', r'보도\s*단차|턱\s*높이'),
 ('횡단보도', r'횡단보도\s*(도색|노면표시)\s*(훼손|마모|파손)'),
 ('자전거', r'(자전거|PM|킥보드)\s*(방치|무단\s*주차)'),
 ('육교', r'육교\s*(파손|고장|보수)'),
 ('지하보도', r'지하보도\s*(파손|고장|보수)'),
 ('교통안전시설', r'(시선유도봉|볼라드|가드레일|반사경)\s*(파손|훼손|고장|전도)'),
]

@dataclass(frozen=True)
class Candidate:
    gid: str
    source_table: str
    source_id: str
    kind: str
    evidence: str
    basis: str


def source_to_kinds(*, gid: str, table: str, rows: Iterable[Mapping]) -> tuple[list[Candidate], list[dict]]:
    if not gid or not isinstance(gid,str): raise ValueError('GID_REQUIRED')
    if table not in {'src_complaint','src_road_hazard','src_obstacle','src_blind_spot','src_fatal_accident','src_hotspot','src_ped_hotspot','src_protection_zone'}:
        raise ValueError('UNKNOWN_SOURCE_TABLE')
    result=[]; unresolved=[]; seen=set()
    for row in rows:
        rid=str(row.get('complaint_id') or row.get('row_id') or row.get('src_id') or '').strip()
        if row.get('gid') != gid or not rid:
            unresolved.append({'source_table':table,'source_id':rid,'reason':'GID_OR_ID_MISMATCH'});continue
        raw=''; kind=None; basis=''
        if table=='src_road_hazard':
            raw=str(row.get('type') or '').strip()
            if raw in {'포트홀','피로균열','수직균열','수평균열'}:
                kind='파손';basis='CONFIRMED_ROAD_SURFACE_DEFECT'
            # Mere delineator or rubbish detection is NOT a confirmed fault.
        elif table=='src_complaint':
            # report_type_raw is classified first; masked_summary only when
            # the classification is already independently verified (not LLM guess).
            raw=str(row.get('report_type_raw') or '').strip()
            for k,pattern in PATTERNS:
                if re.search(pattern,raw,re.IGNORECASE):
                    kind=k;basis='EXPLICIT_REPORT_TYPE';break
            if kind is None and row.get('verified_problem_kind') in KINDS:
                kind=str(row['verified_problem_kind']);basis='EXPLICIT_VERIFIED_KIND'
        elif table=='src_obstacle':
            raw=str(row.get('remark') or '').strip()
            # Do not map any generic obstacle simply to '적치'.
            for k,p in PATTERNS:
                if k in {'적치','노점','주정차','공사','점용'} and re.search(p,raw,re.IGNORECASE):
                    kind=k;basis='EXPLICIT_OBSTACLE_REMARK';break
        elif table=='src_blind_spot':
            raw=str(row.get('remark') or '').strip()
            for k,p in PATTERNS:
                if k in {'주정차','적치','교통안전시설'} and re.search(p,raw,re.IGNORECASE):
                    kind=k;basis='EXPLICIT_CAUSE_REMARK';break
        if kind is None:
            unresolved.append({'source_table':table,'source_id':rid,'reason':'NO_VERIFIED_PROBLEM_KIND'});continue
        identity=(table,rid,kind)
        if identity in seen:continue
        seen.add(identity)
        result.append(Candidate(gid,table,rid,kind,raw[:120],basis))
    return result,unresolved


def jurisdiction_candidates(candidate: Candidate, jurisdiction_rows: Iterable[Mapping], dept_rows: Iterable[Mapping], *, gu: str | None=None, condition_key: str | None=None, condition_verified: bool=False) -> dict:
    """Advisory only: match actual DB87+88, never fabricate 3-key F01 rules.

    DB88 condition_text is free text, not an exact road_kind enum. A nonempty
    condition must be externally verified by F-02/source. Ambiguity blocks.
    """
    j_by_id={str(j.get('jurisdiction_id')): j for j in jurisdiction_rows}
    eligible=[]; blocked=[]
    for jid in JUR[candidate.kind]:
        j=j_by_id.get(jid)
        if j is None:
            blocked.append({'jurisdiction_id':jid,'reason':'MISSING_DB87_ROW'});continue
        rows=[r for r in dept_rows if str(r.get('jurisdiction_id'))==jid]
        if not rows:
            blocked.append({'jurisdiction_id':jid,'reason':'NO_DB88_ROW'});continue
        for d in rows:
            row_gu=str(d.get('gu_name') or '').strip()
            if row_gu and not gu:
                blocked.append({'jurisdiction_id':jid,'reason':'GU_REQUIRED'});continue
            if row_gu and row_gu not in str(gu):continue
            cond=str(d.get('condition_text') or '').strip()
            if cond and (not condition_verified or cond != str(condition_key or '').strip()):
                blocked.append({'jurisdiction_id':jid,'reason':'F02_CONDITION_NOT_VERIFIED'});continue
            # Where the same JUR/gu has both a general row and a qualified
            # alternative, the general row must not silently win.  The source
            # location must be independently verified by F-02 before routing.
            # E.g. JUR-02 in Sujeong-gu has a separate "other neighborhoods" row.
            if not cond and row_gu and any(
                str(other.get('jurisdiction_id')) == jid
                and str(other.get('gu_name') or '').strip() == row_gu
                and str(other.get('condition_text') or '').strip()
                for other in rows
            ):
                blocked.append({'jurisdiction_id':jid,'reason':'GU_CONDITIONAL_BRANCH_REQUIRES_REVIEW'})
                continue
            eligible.append({'jurisdiction_id':jid,'dept_name':d.get('dept_name'),'gu_name':row_gu or None,'source_ref':j.get('basis'),'confirm_status':j.get('confirm_status')})
    # A detected road-surface defect does not establish a sidewalk defect.
    # The only mapped JUR-02 pertains to sidewalk; block this until a separately
    # verified road/sidewalk attribution and matching jurisdiction are available.
    road_surface_unresolved = (
        candidate.source_table == 'src_road_hazard'
        and candidate.kind == '파손'
    )
    if road_surface_unresolved:
        blocked.append({'jurisdiction_id':'JUR-02','reason':'ROAD_VS_SIDEWALK_UNVERIFIED'})
        eligible = []
    if len(eligible)==1 and eligible[0]['confirm_status']=='확인됨':
        status='1차 부서 후보'
    else:
        status='확인 필요'
    return {'status':status,'problem_kind':candidate.kind,'source_id':candidate.source_id,'candidate_departments':eligible,'blocked_conditions':blocked,'department_finalized':False,'needs_human_review':True}
