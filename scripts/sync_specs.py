#!/usr/bin/env python3
"""구글 시트 스펙 탭에서 데이터를 가져와 YAML 파일로 동기화하고 git commit합니다.

Usage:
    python3 sync_specs.py <sheet_csv_url> <specs_dir> <repo_path> [config_path]
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
    'bool': 'boolean',
    'number': 'number',
    'float': 'number',
    'integer': 'integer',
    'int': 'integer',
    'time': 'datetime',
    'datetime': 'datetime',
    'date': 'datetime',
    'timestamp': 'datetime',
}

# config.yaml의 column_map에서 필수로 인식할 값 기본값
DEFAULT_REQUIRED_VALUES = {
    'Y': ['Y', '필수', 'Required', 'required', 'TRUE', 'true', '1', 'O'],
    'N': ['N', '선택', 'Optional', 'optional', 'FALSE', 'false', '0'],
    'CONDITIONAL': ['CONDITIONAL', 'conditional', '조건부'],
}


def load_column_map(config_path: str):
    """config.yaml에서 column_map과 required_values를 읽어온다. 없으면 기본값 반환."""
    col_map = {
        'event_name': ['이벤트 명', '이벤트명', 'event_name', 'Event Name', 'event'],
        'property_key': ['프로퍼티명', 'property_key', 'Property Name', 'key', 'property'],
        'data_type': ['데이터 타입', 'data_type', 'Type', 'type', '타입'],
        'required': ['필수 여부', 'required', 'Required', '필수'],
        'condition': ['내용 조건', 'condition', 'Condition', '조건', '설명', 'description'],
    }
    req_vals = dict(DEFAULT_REQUIRED_VALUES)
    try:
        with open(Path(config_path).expanduser(), encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        sheet_cfg = config.get('sheet') or {}
        for field, val in (sheet_cfg.get('column_map') or {}).items():
            col_map[field] = [val] if isinstance(val, str) else val
        req_vals.update(sheet_cfg.get('required_values') or {})
    except Exception:
        pass
    return col_map, req_vals


def pick_col(row: dict, candidates: list) -> str:
    """후보 컬럼명 목록에서 row에 존재하는 첫 번째 값을 반환."""
    for c in candidates:
        if c in row:
            return (row[c] or '').strip()
    return ''


def normalize_required(val: str, required_values: dict) -> str:
    val = val.strip()
    for canonical, aliases in required_values.items():
        if val in aliases or val.upper() in [a.upper() for a in aliases]:
            return canonical
    return 'N'


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


def parse_sheet(csv_text: str, col_map: dict, required_values: dict) -> dict:
    reader = csv.DictReader(io.StringIO(csv_text))
    events: dict = defaultdict(list)
    seen: set = set()

    for row in reader:
        event_name = pick_col(row, col_map['event_name'])
        prop_key = pick_col(row, col_map['property_key'])
        if not event_name or not prop_key:
            continue
        if (event_name, prop_key) in seen:
            continue
        seen.add((event_name, prop_key))

        raw_type = pick_col(row, col_map['data_type']) or 'string'
        data_type = TYPE_MAP.get(raw_type.lower(), 'string')

        raw_required = pick_col(row, col_map['required']) or 'N'
        required_str = normalize_required(raw_required, required_values)

        condition = pick_col(row, col_map['condition'])

        extras = parse_condition(required_str, condition)
        prop = {'key': prop_key, 'type': data_type}
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


def diff_props(old_content: str, new_props: list) -> list:
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
    total = len(change_map)
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

    body_lines = []
    for event, details in sorted(change_map.items()):
        if details is None:
            body_lines.append(f'- [{event}] 신규 이벤트 추가')
        else:
            for d in details:
                body_lines.append(f'- [{event}] {d}')

    return title + '\n\n' + '\n'.join(body_lines)


def sync(sheet_url: str, specs_dir: str, repo_path: str, config_path: str = '~/.qa-checker/config.yaml'):
    col_map, required_values = load_column_map(config_path)

    print('📥 시트 데이터 가져오는 중...')
    try:
        csv_text = fetch_csv(sheet_url)
    except requests.RequestException as e:
        print(f'❌ 시트 접근 실패: {e}')
        print('시트가 "링크 있는 사람 누구나 보기" 로 설정되어 있는지 확인하세요.')
        sys.exit(1)

    events = parse_sheet(csv_text, col_map, required_values)
    if not events:
        print('❌ 파싱된 이벤트가 없습니다. 시트 헤더 또는 config의 column_map을 확인하세요.')
        print(f'   감지된 컬럼: {", ".join(csv.DictReader(io.StringIO(csv_text)).fieldnames or [])}')
        sys.exit(1)
    print(f'✅ {len(events)}개 이벤트 파싱 완료')

    specs_path = Path(specs_dir)
    change_map: dict = {}

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
        print('Usage: sync_specs.py <sheet_url> <specs_dir> <repo_path> [config_path]')
        sys.exit(1)
    config = sys.argv[4] if len(sys.argv) > 4 else '~/.qa-checker/config.yaml'
    sync(sys.argv[1], sys.argv[2], sys.argv[3], config)
