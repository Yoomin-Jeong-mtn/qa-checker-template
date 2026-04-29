import json
import re
import sys
from datetime import datetime


def _is_datetime(value) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return True
    except ValueError:
        return False


TYPE_CHECKERS = {
    'string': lambda v: isinstance(v, str),
    'boolean': lambda v: isinstance(v, bool),
    'integer': lambda v: isinstance(v, int) and not isinstance(v, bool),
    'number': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    'datetime': _is_datetime,
}


def validate(rows: list, spec: dict, skip_events: list = None) -> dict:
    violations = []
    unknowns: dict = {}
    # conditional 이벤트는 자동으로 skip
    conditional_set = {name for name, props in spec.items() if '__conditional__' in props}
    skip_set = set(skip_events or []) | conditional_set

    for row in rows:
        if row['name'] in skip_set:
            continue
        event_name = row['name']
        event_id = row['event_id']
        properties = row['properties']

        if event_name not in spec:
            key = (event_name, None)
            if key not in unknowns:
                unknowns[key] = {'event_name': event_name, 'key': None, 'sample_values': []}
            continue

        event_spec = spec[event_name]

        for prop_key, prop_def in event_spec.items():
            if prop_key.startswith('__'):
                continue
            condition_when = prop_def.get('condition_when')
            if condition_when:
                cw_met = properties.get(condition_when['key']) == condition_when['value']
                if not cw_met:
                    if prop_key in properties:
                        note = prop_def.get('condition_note', f"{condition_when['key']}={condition_when['value']} 일 때만 수집")
                        violations.append({
                            'event_id': event_id, 'event_name': event_name,
                            'key': prop_key, 'value': properties[prop_key],
                            'error_type': 'unexpected_property',
                            'error_detail': f'조건 미충족 시 수집 불가 ({note})',
                        })
                    continue
            if prop_def.get('required') and prop_key not in properties:
                violations.append({
                    'event_id': event_id,
                    'event_name': event_name,
                    'key': prop_key,
                    'value': None,
                    'error_type': 'missing_required',
                    'error_detail': '필수 프로퍼티 누락',
                })

        for prop_key, value in properties.items():
            if prop_key not in event_spec:
                ukey = (event_name, prop_key)
                if ukey not in unknowns:
                    unknowns[ukey] = {'event_name': event_name, 'key': prop_key, 'sample_values': []}
                if len(unknowns[ukey]['sample_values']) < 3:
                    unknowns[ukey]['sample_values'].append(value)
                continue

            prop_def = event_spec[prop_key]
            condition_when = prop_def.get('condition_when')
            if condition_when:
                cw_met = properties.get(condition_when['key']) == condition_when['value']
                if not cw_met:
                    continue  # unexpected_property는 위 루프에서 이미 처리
            expected_type = prop_def['type']
            allow_empty = prop_def.get('allow_empty', False)

            if value is None or value == '':
                if not allow_empty:
                    violations.append({
                        'event_id': event_id, 'event_name': event_name,
                        'key': prop_key, 'value': value,
                        'error_type': 'empty_not_allowed', 'error_detail': '빈값 허용 안 됨',
                    })
                continue  # 빈값은 type/enum/pattern 검사 생략

            checker = TYPE_CHECKERS.get(expected_type)
            if checker and not checker(value):
                violations.append({
                    'event_id': event_id, 'event_name': event_name,
                    'key': prop_key, 'value': value,
                    'error_type': 'type_mismatch',
                    'error_detail': f'타입 오류 (expected: {expected_type}, got: {type(value).__name__})',
                })
                continue

            enum_vals = prop_def.get('enum')
            if enum_vals and value not in enum_vals:
                violations.append({
                    'event_id': event_id, 'event_name': event_name,
                    'key': prop_key, 'value': value,
                    'error_type': 'enum_mismatch',
                    'error_detail': f'허용값 아님 (enum: {"|".join(str(e) for e in enum_vals)})',
                })
                continue

            pattern = prop_def.get('pattern')
            if pattern and isinstance(value, str) and not re.match(pattern, value):
                violations.append({
                    'event_id': event_id, 'event_name': event_name,
                    'key': prop_key, 'value': value,
                    'error_type': 'pattern_mismatch',
                    'error_detail': f'패턴 불일치 (pattern: {pattern})',
                })

            for rule in prop_def.get('value_rules', []):
                if_contains = rule.get('if_contains', [])
                if not isinstance(value, str):
                    continue
                if not any(kw in value for kw in if_contains):
                    continue
                must_match = rule.get('must_match')
                if must_match and not re.search(must_match, value):
                    violations.append({
                        'event_id': event_id, 'event_name': event_name,
                        'key': prop_key, 'value': value,
                        'error_type': 'value_rule_mismatch',
                        'error_detail': f'조건부 패턴 누락 — "{"|".join(if_contains)}" 포함 시 "{must_match}" 필요',
                    })

    return {
        'violations': violations,
        'unknowns': list(unknowns.values()),
        'total_rows': len(rows),
        'skipped_conditional': [
            {'event': name, 'condition_note': spec[name]['__conditional__']['condition_note']}
            for name in sorted(conditional_set)
            if name in spec
        ],
    }


if __name__ == '__main__':
    rows = json.loads(sys.argv[1])
    spec = json.loads(sys.argv[2])
    skip_events = json.loads(sys.argv[3]) if len(sys.argv) > 3 else []
    print(json.dumps(validate(rows, spec, skip_events), ensure_ascii=False))
