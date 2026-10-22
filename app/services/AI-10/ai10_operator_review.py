"""AI-10 6단계: 오프라인 운영자 검토/승인 실습용 저장소 (운영 DB 미연결).

실행: uv run python app/services/ai10_operator_review.py --help
Python 표준 라이브러리만 사용합니다.
"""
import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'data' / 'ai10_review_report_v3.json'
STORE = ROOT / 'data' / 'ai10_operator_review_dev.json'


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def atomic_save(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix='.ai10_review_', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def bootstrap(source=SOURCE, store=STORE):
    if store.exists():
        raise ValueError('검토 저장소가 이미 있습니다. 원본 보존을 위해 초기화를 중단합니다.')
    report = read_json(source)
    rows = report.get('results', [])
    ids = [x.get('rule_id') for x in rows]
    if not rows or len(ids) != len(set(ids)) or any(not x for x in ids):
        raise ValueError('원본 보고서의 CK 식별자가 올바르지 않습니다.')
    items = {}
    for x in rows:
        if x.get('technical_status') != 'generated' or not x.get('draft_template'):
            raise ValueError(f"{x.get('rule_id')} 생성 결과 없음")
        rid = x['rule_id']
        items[rid] = {
            'rule_id': rid,
            'source_draft_template': x['draft_template'],
            'edited_template': x['draft_template'],
            'review_note': x.get('review_note', ''),
            'findings': x.get('findings', []),
            'review_status': 'pending',
            'approved': False,
            'reviewer': None,
            'approved_at': None,
            'revision': 0,
            'events': [],
        }
    payload = {'purpose': '개발 전용: 운영 DB/후보 상세 ⑥ 미연결',
               'source_report': source.name, 'created_at': now(), 'items': items}
    atomic_save(store, payload)
    return len(items)


def load_store(store=STORE):
    if not store.exists():
        raise ValueError('검토 저장소가 없습니다. init부터 실행하세요.')
    return read_json(store)


def get_item(data, rid):
    try:
        return data['items'][rid]
    except KeyError:
        raise ValueError(f'존재하지 않는 CK 번호: {rid}') from None


def record(item, action, reviewer, note=''):
    item['events'].append({'at': now(), 'action': action, 'reviewer': reviewer,
                           'note': note, 'revision': item['revision']})


def update_text(rid, content, reviewer, store=STORE):
    if not reviewer.strip() or not content.strip():
        raise ValueError('검토자와 수정 문장을 입력해야 합니다.')
    data = load_store(store)
    item = get_item(data, rid)
    if item['review_status'] == 'approved':
        raise ValueError('승인 문장은 직접 수정할 수 없습니다. 승인 취소 후 수정하세요.')
    if content == item['edited_template']:
        raise ValueError('문장이 이전과 같습니다. 변경 사항이 없습니다.')
    item['edited_template'] = content.strip()
    item['revision'] += 1
    item['review_status'] = 'pending'
    item['approved'] = False
    item['reviewer'] = reviewer.strip()
    record(item, 'edited', reviewer.strip())
    atomic_save(store, data)


def decide(rid, reviewer, decision, note='', acknowledge=False, store=STORE, *, evidence_source='', evidence_checked=False):
    if not reviewer.strip():
        raise ValueError('검토자 식별값이 필요합니다.')
    if decision not in ('approve', 'reject', 'revoke'):
        raise ValueError('알 수 없는 결정입니다.')
    data = load_store(store)
    item = get_item(data, rid)
    if decision == 'approve':
        if item['approved']:
            raise ValueError('이미 승인된 항목입니다.')
        if not evidence_source.strip() or not evidence_checked:
            raise ValueError('승인하려면 근거 출처와 운영자 원문 대조 확인이 필요합니다.')
        if item['findings'] and not acknowledge:
            raise ValueError('검토 표시가 있습니다. 검토 후 --ack-findings를 명시해야 승인 가능합니다.')
        if not note.strip():
            raise ValueError('승인 근거(--note)를 입력해야 합니다.')
        item['review_status'], item['approved'] = 'approved', True
        item['approved_at'] = now()
    elif decision == 'reject':
        if not note.strip():
            raise ValueError('반려 사유(--note)를 입력해야 합니다.')
        if item['approved']:
            raise ValueError('승인 문장은 먼저 revoke로 승인 취소해야 합니다.')
        item['review_status'], item['approved'] = 'rejected', False
        item['approved_at'] = None
    else:
        if not item['approved']:
            raise ValueError('승인된 문장만 승인 취소할 수 있습니다.')
        if not note.strip():
            raise ValueError('승인 취소 사유(--note)를 입력해야 합니다.')
        item['review_status'], item['approved'] = 'pending', False
        item['approved_at'] = None
    item['reviewer'] = reviewer.strip()
    record(item, decision, reviewer.strip(), note)
    if decision == 'approve':
        item['events'][-1]['evidence_source'] = evidence_source.strip()
        item['events'][-1]['evidence_checked_by_reviewer'] = True
    atomic_save(store, data)


def cli():
    parser = argparse.ArgumentParser(description='AI-10 개발용 오프라인 운영자 검토 (DB 미연결)')
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--store', type=Path, default=STORE)
    subs = parser.add_subparsers(dest='command', required=True)
    subs.add_parser('init')
    subs.add_parser('list')
    view = subs.add_parser('show')
    view.add_argument('rule_id')
    edit = subs.add_parser('edit')
    edit.add_argument('rule_id')
    edit.add_argument('--reviewer', required=True)
    text_group = edit.add_mutually_exclusive_group(required=True)
    text_group.add_argument('--text')
    text_group.add_argument('--text-file', type=Path)
    for name in ('approve', 'reject', 'revoke'):
        sub = subs.add_parser(name)
        sub.add_argument('rule_id')
        sub.add_argument('--reviewer', required=True)
        sub.add_argument('--note', required=True)
        if name == 'approve':
            sub.add_argument('--ack-findings', action='store_true')
            sub.add_argument('--evidence-source', required=True)
            sub.add_argument('--evidence-checked', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'init':
            print(f'초기화 완료: {bootstrap(args.source, args.store)}건 | {args.store}')
            return
        data = load_store(args.store)
        if args.command == 'list':
            for rid, item in sorted(data['items'].items()):
                print(f"{rid} | {item['review_status']} | 검토 표시 {len(item['findings'])}건 | 수정 {item['revision']}회")
        elif args.command == 'show':
            print(json.dumps(get_item(data, args.rule_id), ensure_ascii=False, indent=2))
        elif args.command == 'edit':
            content = args.text if args.text is not None else args.text_file.read_text(encoding='utf-8-sig')
            update_text(args.rule_id, content, args.reviewer, args.store)
            print(f'{args.rule_id} 수정 저장 완료 (미승인 유지)')
        else:
            decide(args.rule_id, args.reviewer, args.command, args.note,
                   getattr(args, 'ack_findings', False), args.store,
                   evidence_source=getattr(args, 'evidence_source', ''),
                   evidence_checked=getattr(args, 'evidence_checked', False))
            print(f'{args.rule_id} 처리 완료: {args.command} (개발용 JSON에만 저장)')
    except (ValueError, FileNotFoundError) as e:
        parser.exit(1, f'오류: {e}\n')


if __name__ == '__main__':
    cli()
