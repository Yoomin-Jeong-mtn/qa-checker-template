#!/usr/bin/env python3
"""YAML 스펙 파일을 구글 시트에 동기화합니다.

Usage:
    python3 sync_yaml_to_sheet.py <specs_dir> <sheet_id> <tab_name> <service_account_path>
"""

import sys
from pathlib import Path

import gspread
import yaml
from google.oauth2.service_account import Credentials

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

HEADERS = ['이벤트 명', '프로퍼티명', '데이터 타입', '필수 여부', '내용 조건']

TYPE_REVERSE = {
    'string': 'string',
    'boolean': 'boolean',
    'number': 'number',
    'integer': 'integer',
    'datetime': 'time',
}


def open_sheet(sheet_id, tab_name, service_account_path):
    creds = Credentials.from_service_account_file(
        str(Path(service_account_path).expanduser()), scopes=SCOPES
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    try:
        return sh.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=tab_name, rows=1000, cols=len(HEADERS))


def prop_to_row(event_name, prop):
    data_type = TYPE_REVERSE.get(prop.get('type', 'string'), 'string')

    required = prop.get('required', False)
    allow_empty = prop.get('allow_empty', True)
    if required:
        required_str = 'Y'
    elif not allow_empty:
        required_str = 'N'
    else:
        required_str = 'CONDITIONAL' if not required else 'N'

    conditions = []
    if prop.get('enum'):
        conditions.append(f"enum: {', '.join(str(e) for e in prop['enum'])}")
    if prop.get('pattern'):
        conditions.append(f"regex: {prop['pattern']}")
    for rule in prop.get('value_rules', []):
        kws = ' / '.join(rule.get('if_contains', []))
        must = rule.get('must_match', '')
        conditions.append(f"if_contains({kws}) → must_match: {must}")

    return [event_name, prop.get('key', ''), data_type, required_str, ' / '.join(conditions)]


def load_specs(specs_dir):
    specs_path = Path(specs_dir)
    rows = []

    # _common.yaml에서 공통 그룹 로드
    common_groups = {}
    common_path = specs_path / '_common.yaml'
    if common_path.exists():
        with open(common_path, encoding='utf-8') as f:
            common_data = yaml.safe_load(f)
        common_groups = common_data.get('properties', {})

    for yaml_file in sorted(specs_path.glob('*.yaml')):
        if yaml_file.name.startswith('_'):
            continue
        with open(yaml_file, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if not data or 'event' not in data:
            continue

        event_name = data['event']
        props = []

        extends = data.get('extends')
        if extends and extends in common_groups:
            props.extend(common_groups[extends])

        props.extend(data.get('properties') or [])

        for prop in props:
            rows.append(prop_to_row(event_name, prop))

    return rows


def sync(specs_dir, sheet_id, tab_name, service_account_path):
    print('📂 YAML 스펙 로드 중...')
    data_rows = load_specs(specs_dir)
    print(f'✅ {len(data_rows)}개 프로퍼티 행 준비 완료')

    print('📊 구글 시트 연결 중...')
    ws = open_sheet(sheet_id, tab_name, service_account_path)

    all_rows = [HEADERS] + data_rows
    ws.clear()
    ws.update(all_rows, value_input_option='RAW')

    print(f'✅ 시트 업데이트 완료: {tab_name} ({len(data_rows)}행)')


if __name__ == '__main__':
    if len(sys.argv) < 5:
        print('Usage: sync_yaml_to_sheet.py <specs_dir> <sheet_id> <tab_name> <service_account_path>')
        sys.exit(1)
    sync(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
