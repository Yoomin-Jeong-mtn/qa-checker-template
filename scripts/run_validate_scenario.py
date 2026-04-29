"""validate_scenario를 파일 경로로 호출하는 래퍼"""
import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))
from validate_scenario import load_scenarios, find_scenario, validate_scenario

rows_file, spec_file, scenario_name, specs_dir = sys.argv[1:5]

with open(rows_file, encoding='utf-8') as f:
    rows = json.load(f)
with open(spec_file, encoding='utf-8') as f:
    spec = json.load(f)

scenarios = load_scenarios(specs_dir)
scenario = find_scenario(scenarios, scenario_name)

if not scenario:
    print(json.dumps({'error': f'시나리오를 찾을 수 없습니다: {scenario_name}'}, ensure_ascii=False))
    sys.exit(1)

result = validate_scenario(rows, spec, scenario)
print(json.dumps(result, ensure_ascii=False))
