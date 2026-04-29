"""시나리오 기반 검증: 수집 여부 + 데이터 타입 체크"""
import json
import sys
from pathlib import Path

import yaml

from validate import validate


def load_scenarios(specs_dir: str) -> list:
    scenarios_dir = Path(specs_dir) / 'scenarios'
    if not scenarios_dir.exists():
        return []
    scenarios = []
    for yaml_file in sorted(scenarios_dir.glob('*.yaml')):
        with open(yaml_file, encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if data and 'name' in data:
            scenarios.append(data)
    return scenarios


def find_scenario(scenarios: list, name: str):
    for s in scenarios:
        if s['name'] == name:
            return s
    return None


def validate_scenario(rows: list, spec: dict, scenario: dict) -> dict:
    expected_events = scenario['events']
    skip_conditional = scenario.get('skip_conditional', False)

    # conditional 이벤트 목록
    conditional_events = {
        event for event in expected_events
        if spec.get(event, {}).get('__conditional__')
    }

    # 수집 여부 체크 대상 (conditional 제외)
    check_presence = set(expected_events)
    if skip_conditional:
        check_presence -= conditional_events

    # CSV에서 발생한 이벤트
    fired_events = {row['name'] for row in rows}

    # 미수집 이벤트
    missing_events = [
        e for e in sorted(check_presence)
        if e not in fired_events
    ]

    # 포맷 검증 (시나리오 이벤트만, conditional은 자동 skip)
    scenario_rows = [r for r in rows if r['name'] in set(expected_events)]
    format_result = validate(scenario_rows, spec)

    return {
        'scenario': scenario['name'],
        'total_rows': len(scenario_rows),
        'missing_events': missing_events,
        'skipped_conditional': sorted(conditional_events) if skip_conditional else [],
        'violations': format_result['violations'],
        'unknowns': format_result['unknowns'],
    }


if __name__ == '__main__':
    rows = json.loads(sys.argv[1])
    spec = json.loads(sys.argv[2])
    scenario_name = sys.argv[3]
    specs_dir = sys.argv[4]

    scenarios = load_scenarios(specs_dir)
    scenario = find_scenario(scenarios, scenario_name)

    if not scenario:
        print(json.dumps({'error': f'시나리오를 찾을 수 없습니다: {scenario_name}'}, ensure_ascii=False))
        sys.exit(1)

    result = validate_scenario(rows, spec, scenario)
    print(json.dumps(result, ensure_ascii=False))
