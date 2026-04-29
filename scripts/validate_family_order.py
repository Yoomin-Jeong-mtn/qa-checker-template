"""패밀리 주문 시나리오 검증: order_no 기반 멤버/리더 역할 분리"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import yaml

KST = timezone(timedelta(hours=9))


def load_scenario(specs_dir, scenario_name):
    for yaml_file in (Path(specs_dir) / 'scenarios').glob('*.yaml'):
        with open(yaml_file, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if data and data.get('name') == scenario_name:
            return data
    return None


def fetch_braze_user(braze_id, api_key, server):
    resp = requests.post(
        f'https://rest.{server}.braze.com/users/export/ids',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={'braze_id': braze_id, 'fields_to_export': ['braze_id', 'custom_attributes']},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get('message') != 'success':
        raise RuntimeError(f"Braze API error: {data.get('message')}")
    users = data.get('users', [])
    return users[0] if users else None


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


def group_by_order_no(rows):
    groups = {}
    for row in rows:
        order_no = row.get('properties', {}).get('order_no')
        if order_no:
            groups.setdefault(str(order_no), []).append(row)
    return groups


def detect_phase(event_names, phase_detection):
    for phase, triggers in phase_detection.items():
        if any(e in event_names for e in triggers):
            return phase
    return 'request'


def get_user_roles(user_ids, api_key, server):
    roles = {}
    for uid in user_ids:
        if not uid:
            continue
        user = fetch_braze_user(uid, api_key, server)
        if user:
            custom_attrs = user.get('custom_attributes', {})
            roles[uid] = {
                'is_leader': bool(custom_attrs.get('is_family_leader', False)),
                'custom_attributes': custom_attrs,
            }
    return roles


def check_events(role_rows, phase_role_spec, spec):
    required = phase_role_spec.get('events', [])
    fired = {r['name'] for r in role_rows}
    missing = [e for e in required if e not in fired]

    violations = []
    for row in role_rows:
        event_name = row['name']
        event_spec = spec.get(event_name, {})
        props = row.get('properties', {})

        for prop_key, prop_def in event_spec.items():
            if prop_key.startswith('__'):
                continue
            if prop_def.get('required') and prop_key not in props:
                violations.append({
                    'event': event_name,
                    'event_id': row.get('event_id', ''),
                    'key': prop_key,
                    'error': '필수 프로퍼티 누락',
                    'spec': f'required: true, type: {prop_def.get("type", "?")}',
                })
            elif prop_key in props:
                value = props[prop_key]
                enum_vals = prop_def.get('enum')
                if enum_vals and value not in enum_vals:
                    violations.append({
                        'event': event_name,
                        'event_id': row.get('event_id', ''),
                        'key': prop_key,
                        'error': f'허용값 아님 (actual: {value})',
                        'spec': f'enum: {"|".join(str(e) for e in enum_vals)}',
                    })

    return missing, violations


def cross_check(member_rows, leader_rows, cross_check_spec):
    violations = []
    for cc in cross_check_spec:
        leader_event = cc['event']
        member_event = cc['against']
        fields = cc['fields']

        l_rows = [r for r in leader_rows if r['name'] == leader_event]
        m_rows = [r for r in member_rows if r['name'] == member_event]

        if not l_rows or not m_rows:
            continue

        m_props = m_rows[0].get('properties', {})
        for l_row in l_rows:
            l_props = l_row.get('properties', {})
            for field in fields:
                if l_props.get(field) != m_props.get(field):
                    violations.append({
                        'event': leader_event,
                        'key': field,
                        'error': f'멤버 {member_event}와 불일치 (리더: {l_props.get(field)}, 멤버: {m_props.get(field)})',
                    })
    return violations


def check_logpurchase(role_rows, logpurchase_check):
    violations = []
    pid = logpurchase_check.get('pid')
    check_negative = logpurchase_check.get('amount') == 'negative'

    lp_rows = [r for r in role_rows if r['name'] == 'order_v2']
    if not lp_rows:
        return [{'event': 'order_v2', 'key': None, 'error': '미수집', 'spec': f'pid: {pid}'}]

    for row in lp_rows:
        props = row.get('properties', {})
        if pid and props.get('pid') != pid:
            violations.append({
                'event': 'order_v2',
                'event_id': row.get('event_id', ''),
                'key': 'pid',
                'error': f'pid 불일치 (expected: {pid}, actual: {props.get("pid")})',
                'spec': f'expected pid: {pid}',
            })
        if check_negative:
            price = props.get('price') or props.get('p') or props.get('amount')
            if price is not None and float(price) >= 0:
                violations.append({
                    'event': 'order_v2',
                    'event_id': row.get('event_id', ''),
                    'key': 'price',
                    'error': f'취소 건 음수 금액 필요 (actual: {price})',
                    'spec': 'amount: negative',
                })
    return violations


def check_attributes(attr_checks, role_rows, custom_attrs):
    violations = []
    for check in attr_checks:
        key = check['key']
        check_type = check.get('check')
        trigger_event = check.get('trigger_event')
        trigger_rows = [r for r in role_rows if r['name'] == trigger_event] if trigger_event else []

        if check_type in ('array_last_item_field_equals', 'array_not_contains'):
            if not trigger_rows:
                continue
            match_field = check['match_field']
            trigger_props = trigger_rows[-1].get('properties', {})
            expected_value = trigger_props.get(match_field)
            history = custom_attrs.get(key, [])

            if check_type == 'array_last_item_field_equals':
                if not history:
                    violations.append({'key': key, 'error': f'{key} 배열이 비어있음'})
                elif history[-1].get(match_field) != expected_value:
                    violations.append({
                        'key': key,
                        'error': f'맨끝 항목 {match_field} 불일치 (expected: {expected_value}, actual: {history[-1].get(match_field)})',
                    })
            elif check_type == 'array_not_contains':
                if any(item.get(match_field) == expected_value for item in history):
                    violations.append({
                        'key': key,
                        'error': f'취소된 상품이 {key}에 남아있음 ({match_field}: {expected_value})',
                    })

        elif check.get('expected') == 'event_date_kst':
            if not trigger_rows:
                continue
            trigger_time = max((r['time'] for r in trigger_rows if r.get('time')), default=None)
            event_date = to_kst_date(trigger_time)
            actual = custom_attrs.get(key)
            actual_date = to_kst_date(str(actual)) if actual else None
            if actual_date != event_date:
                violations.append({
                    'key': key,
                    'error': f'날짜 불일치 (expected: {event_date}, actual: {actual_date})',
                })

    return violations


def validate_family_order(rows, scenario, spec, api_key, server):
    phase_detection = scenario.get('phase_detection', {})
    phases = scenario['phases']

    by_order = group_by_order_no(rows)
    all_user_ids = {r['user_id'] for r in rows if r.get('user_id')}
    user_roles = get_user_roles(all_user_ids, api_key, server)

    results = []

    for order_no, order_rows in sorted(by_order.items()):
        all_event_names = {r['name'] for r in order_rows}
        terminal_phase = detect_phase(all_event_names, phase_detection)

        member_rows = [r for r in order_rows if not user_roles.get(r['user_id'], {}).get('is_leader')]
        leader_rows = [r for r in order_rows if user_roles.get(r['user_id'], {}).get('is_leader')]

        member_uid = member_rows[0]['user_id'] if member_rows else None
        leader_uid = leader_rows[0]['user_id'] if leader_rows else None

        order_result = {
            'order_no': order_no,
            'phase': terminal_phase,
            'member': {
                'user_id': member_uid,
                'events': sorted({r['name'] for r in member_rows}),
                'missing_events': [],
                'violations': [],
                'attribute_violations': [],
            },
            'leader': {
                'user_id': leader_uid,
                'events': sorted({r['name'] for r in leader_rows}),
                'missing_events': [],
                'violations': [],
                'cross_check_violations': [],
                'attribute_violations': [],
            },
        }

        # request + terminal phase 순서로 검증
        phases_to_check = ['request'] if terminal_phase == 'request' else ['request', terminal_phase]

        for phase_name in phases_to_check:
            phase_spec = phases.get(phase_name, {})

            # 멤버 검증
            member_spec = phase_spec.get('member', {})
            if member_spec and member_rows:
                missing, violations = check_events(member_rows, member_spec, spec)
                order_result['member']['missing_events'].extend(missing)
                order_result['member']['violations'].extend(violations)

                attr_checks = member_spec.get('attribute_checks', [])
                if attr_checks and member_uid:
                    custom_attrs = user_roles.get(member_uid, {}).get('custom_attributes', {})
                    order_result['member']['attribute_violations'].extend(
                        check_attributes(attr_checks, member_rows, custom_attrs)
                    )

            # 리더 검증
            leader_spec = phase_spec.get('leader', {})
            if leader_spec and leader_rows:
                missing, violations = check_events(leader_rows, leader_spec, spec)
                order_result['leader']['missing_events'].extend(missing)
                order_result['leader']['violations'].extend(violations)

                logpurchase_check = leader_spec.get('logpurchase_check')
                if logpurchase_check:
                    order_result['leader']['violations'].extend(
                        check_logpurchase(leader_rows, logpurchase_check)
                    )

                attr_checks = leader_spec.get('attribute_checks', [])
                if attr_checks and leader_uid:
                    custom_attrs = user_roles.get(leader_uid, {}).get('custom_attributes', {})
                    order_result['leader']['attribute_violations'].extend(
                        check_attributes(attr_checks, leader_rows, custom_attrs)
                    )

                cc_spec = leader_spec.get('cross_check', [])
                if cc_spec:
                    order_result['leader']['cross_check_violations'].extend(
                        cross_check(member_rows, leader_rows, cc_spec)
                    )

        results.append(order_result)

    return results


if __name__ == '__main__':
    rows = json.loads(sys.argv[1])
    spec = json.loads(sys.argv[2])
    scenario_name = sys.argv[3]
    specs_dir = sys.argv[4]
    api_key = sys.argv[5]
    server = sys.argv[6]

    scenario = load_scenario(specs_dir, scenario_name)
    if not scenario:
        print(json.dumps({'error': f'시나리오를 찾을 수 없습니다: {scenario_name}'}, ensure_ascii=False))
        sys.exit(1)

    result = validate_family_order(rows, scenario, spec, api_key, server)
    print(json.dumps(result, ensure_ascii=False))
