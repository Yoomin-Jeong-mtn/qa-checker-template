#!/usr/bin/env python3
"""구글 시트 스펙 탭에서 데이터를 가져와 YAML 파일로 동기화하고 git commit합니다.

Usage:
    python3 sync_specs.py <sheet_csv_url> <specs_dir> <repo_path>
"""

import csv
import io
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import requests
import yaml

TYPE_MAP = {
    'string': 'string',
    'boolean': 'boolean',
    'number': 'number',
    'integer': 'integer',
    'time': 'datetime',
    'datetime': 'datetime',
}


def fetch_csv(url: str) -> str:
    resp = requests.get(url, allow_redirects=True, timeout=30)
    resp.raise_for_status()
    resp.encoding = 'utf-8'
    return resp.text


def parse_condition(required_str: str, condition: str) -> dict:
    required_str = required_str.strip().upper()
    condition = (condition or '').strip()

    if required_str == 'CONDITIONAL':
        return {'required': False, 'allow_empty': True}

    required = (required_str == 'Y')
    result = {'required': required, 'allow_empty': not required}

    enum_match = re.search(r'enum:\s*([^\n(]+)', condition, re.IGNORECASE)
    if enum_match:
        vals = [v.strip() for v in enum_match.group(1).split(',') if v.strip()]
        if vals:
            result['enum'] = vals

    pattern_match = re.search(r'regex:\s*(\S+)', condition, re.IGNORECASE)
    if pattern_match:
        pat = pattern_match.group(1)
        if pat.startswith('^'):
            result['pattern'] = pat

    return result


def parse_sheet(csv_text: str) -> dict:
    reader = csv.DictReader(io.StringIO(csv_text))
    events: dict = defaultdict(list)
    seen: set = set()

    for row in reader:
        event_name = (row.get('이벤트 명') or row.get('이벤트명') or '').strip()
        prop_key = (row.get('프로퍼티명') or '').strip()
        if not event_name or not prop_key:
            continue
        if (event_name, prop_key) in seen:
            continue
        seen.add((event_name, prop_key))

        data_type = (row.get('데이터 타입') or 'string').strip().lower()
        required_str = (row.get('필수 여부') or 'N').strip()
        condition = (row.get('내용 조건') or '').strip()

        extras = parse_condition(required_str, condition)
        prop = {'key': prop_key, 'type': TYPE_MAP.get(data_type, 'string')}
        prop.update(extras)
        events[event_name].append(prop)

    return dict(events)


def dump_event_yaml(event_name: str, props: list) -> str:
    return yaml.dump(
        {'event': event_name, 'properties': props},
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )


def diff_props(old_content: str, new_props: list) -> list[str]:
    """기존 YAML과 새 props를 비교해 변경사항 요약 문자열 목록 반환."""
    try:
        old_data = yaml.safe_load(old_content)
        old_map = {p['key']: p for p in (old_data.get('properties') or [])}
    except Exception:
        return ['내용 변경']

    new_map = {p['key']: p for p in new_props}
    changes = []

    for key in new_map:
        if key not in old_map:
            changes.append(f'{key} 추가')

    for key in old_map:
        if key not in new_map:
            changes.append(f'{key} 삭제')

    for key in new_map:
        if key not in old_map:
            continue
        old, new = old_map[key], new_map[key]
        if old.get('type') != new.get('type'):
            changes.append(f'{key} 타입 {old.get("type")}→{new.get("type")}')
        if old.get('required') != new.get('required'):
            before = '필수' if old.get('required') else '선택'
            after = '필수' if new.get('required') else '선택'
            changes.append(f'{key} {before}→{after}')
        if old.get('enum') != new.get('enum'):
            changes.append(f'{key} enum 변경')
        if old.get('pattern') != new.get('pattern'):
            changes.append(f'{key} pattern 변경')

    return changes


def build_commit_message(change_map: dict) -> str:
    """change_map: {event_name: [change_str, ...] | None(신규)}"""
    total = len(change_map)

    # 커밋 제목 생성
    all_details = []
    for event, details in sorted(change_map.items()):
        if details is None:
            all_details.append(f'{event}: 신규')
        else:
            for d in details:
                all_details.append(f'{event}: {d}')

    if len(all_details) == 1:
        title = f'chore: sync specs - {all_details[0]}'
    elif total == 1:
        event = list(change_map)[0]
        n = len(change_map[event] or [])
        label = '신규' if change_map[event] is None else f'{n}개 변경'
        title = f'chore: sync specs - {event} {label}'
    else:
        events_str = ', '.join(sorted(change_map)[:3])
        suffix = f' 외 {total - 3}개' if total > 3 else ''
        title = f'chore: sync specs - {total}개 이벤트 변경 ({events_str}{suffix})'

    # 본문 상세 내역
    body_lines = []
    for event, details in sorted(change_map.items()):
        if details is None:
            body_lines.append(f'- [{event}] 신규 이벤트 추가')
        else:
            for d in details:
                body_lines.append(f'- [{event}] {d}')

    return title + '\n\n' + '\n'.join(body_lines)


def sync(sheet_url: str, specs_dir: str, repo_path: str):
    print('📥 시트 데이터 가져오는 중...')
    try:
        csv_text = fetch_csv(sheet_url)
    except requests.RequestException as e:
        print(f'❌ 시트 접근 실패: {e}')
        print('시트가 "링크 있는 사람 누구나 보기" 로 설정되어 있는지 확인하세요.')
        sys.exit(1)

    events = parse_sheet(csv_text)
    if not events:
        print('❌ 파싱된 이벤트가 없습니다. 시트 헤더를 확인하세요.')
        sys.exit(1)
    print(f'✅ {len(events)}개 이벤트 파싱 완료')

    specs_path = Path(specs_dir)
    change_map: dict = {}  # {event_name: [변경사항] or None(신규)}

    for event_name, props in sorted(events.items()):
        file_path = specs_path / f'{event_name}.yaml'
        new_content = dump_event_yaml(event_name, props)

        if file_path.exists():
            old_content = file_path.read_text(encoding='utf-8')
            if old_content == new_content:
                continue
            details = diff_props(old_content, props)
            change_map[event_name] = details
            print(f'  ✏️  업데이트: {event_name}.yaml')
            for d in details:
                print(f'       · {d}')
        else:
            change_map[event_name] = None
            print(f'  ➕ 신규: {event_name}.yaml')

        file_path.write_text(new_content, encoding='utf-8')

    if not change_map:
        print('변경 사항 없음. 커밋 생략.')
        return

    subprocess.run(['git', 'add', 'specs/'], cwd=repo_path, check=True)
    commit_msg = build_commit_message(change_map)
    subprocess.run(['git', 'commit', '-m', commit_msg], cwd=repo_path, check=True)
    print(f'\n✅ {len(change_map)}개 이벤트 변경사항 커밋 완료')
    print('git push를 실행하면 팀원들에게 반영됩니다.')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('Usage: sync_specs.py <sheet_url> <specs_dir> <repo_path>')
        sys.exit(1)
    sync(sys.argv[1], sys.argv[2], sys.argv[3])
