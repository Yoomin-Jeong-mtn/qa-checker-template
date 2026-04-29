"""이벤트 발생 후 Braze 유저 어트리뷰트 검증"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import yaml

KST = timezone(timedelta(hours=9))


def load_attribute_checks(specs_dir, scenario_name):
    scenarios_dir = Path(specs_dir) / 'scenarios'
    if not scenarios_dir.exists():
        return None
    for yaml_file in scenarios_dir.glob('*.yaml'):
        with open(yaml_file, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if data and data.get('name') == scenario_name:
            checks = data.get('attribute_checks')
            return checks
    return None


def fetch_braze_user(braze_id, api_key, server):
    url = f'https://rest.{server}.braze.com/users/export/ids'
    payload = {
        'braze_id': braze_id,
        'fields_to_export': ['braze_id', 'custom_attributes'],
    }
    resp = requests.post(
        url,
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get('message') != 'success':
        raise RuntimeError(f"Braze API error: {data.get('message')}")
    users = data.get('users', [])
    return users[0] if users else None


def get_last_event_time(rows, user_id, event_name):
    times = [r['time'] for r in rows if r['name'] == event_name and r.get('user_id') == user_id and r.get('time')]
    return max(times) if times else None


def to_kst_date(time_str):
    if not time_str:
        return None
    try:
        dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(KST).strftime('%Y-%m-%d')
    except Exception:
        return None


def check_attr_value(actual, expected, trigger_time=None):
    if expected == 'event_date_kst':
        event_date = to_kst_date(trigger_time)
        actual_date = to_kst_date(actual) if isinstance(actual, str) else None
        return actual_date == event_date, f'이벤트 발생일({event_date}) 불일치 (actual: {actual_date})'
    if expected is None:
        ok = actual is None or actual == ''
        return ok, f'null/empty 이어야 함 (actual: {actual})'
    ok = actual == expected
    return ok, f'기대값 불일치 (expected: {expected}, actual: {actual})'


def validate_attributes(rows, checks, api_key, server):
    violations = []

    for check in checks:
        trigger_event = check['trigger_event']
        cancel_event = check.get('cancel_event')
        expected_attrs = check['attributes']
        on_cancel_attrs = check.get('on_cancel', [])

        matching_rows = [r for r in rows if r['name'] == trigger_event]
        if not matching_rows:
            continue

        user_ids = list({r['user_id'] for r in matching_rows if r.get('user_id')})

        for user_id in user_ids:
            trigger_time = get_last_event_time(rows, user_id, trigger_event)
            cancel_time = get_last_event_time(rows, user_id, cancel_event) if cancel_event else None
            cancelled = bool(trigger_time and cancel_time and cancel_time > trigger_time)

            # cancel 발생 시 on_cancel 규칙으로 전환
            attrs_to_check = on_cancel_attrs if cancelled and on_cancel_attrs else expected_attrs
            if cancelled and not on_cancel_attrs:
                continue

            user = fetch_braze_user(user_id, api_key, server)

            if not user:
                violations.append({
                    'user_id': user_id,
                    'event': trigger_event,
                    'key': None,
                    'error': '유저 없음 (Braze에서 조회 불가)',
                })
                continue

            custom_attrs = user.get('custom_attributes', {})
            for attr_rule in attrs_to_check:
                key = attr_rule['key']
                expected = attr_rule['expected']
                actual = custom_attrs.get(key)

                ok, error_msg = check_attr_value(actual, expected, trigger_time)
                if not ok:
                    violations.append({
                        'user_id': user_id,
                        'event': trigger_event,
                        'key': key,
                        'error': error_msg,
                    })

    return {'attribute_violations': violations}


if __name__ == '__main__':
    rows = json.loads(sys.argv[1])
    specs_dir = sys.argv[2]
    scenario_name = sys.argv[3]
    api_key = sys.argv[4]
    server = sys.argv[5]

    checks = load_attribute_checks(specs_dir, scenario_name)
    if checks is None:
        print(json.dumps({'attribute_violations': []}, ensure_ascii=False))
        sys.exit(0)

    result = validate_attributes(rows, checks, api_key, server)
    print(json.dumps(result, ensure_ascii=False))
