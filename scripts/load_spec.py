import json
import sys
from pathlib import Path

import yaml


def load_spec(specs_dir: str) -> dict:
    specs_path = Path(specs_dir)

    common_groups: dict = {}
    common_path = specs_path / '_common.yaml'
    if common_path.exists():
        with open(common_path, encoding='utf-8') as f:
            common_data = yaml.safe_load(f)
        common_groups = common_data.get('properties', {})

    spec: dict = {}
    for yaml_file in specs_path.glob('*.yaml'):
        if yaml_file.name.startswith('_'):
            continue
        with open(yaml_file, encoding='utf-8') as f:
            event_data = yaml.safe_load(f)

        if not event_data or 'event' not in event_data:
            continue
        event_name = event_data['event']
        props: list = []

        extends = event_data.get('extends')
        if extends and extends in common_groups:
            props.extend(common_groups[extends])

        props.extend(event_data.get('properties') or [])
        spec[event_name] = {p['key']: p for p in props}

        if event_data.get('conditional'):
            spec[event_name]['__conditional__'] = {
                'conditional': True,
                'condition_note': event_data.get('condition_note', ''),
            }

    return spec


if __name__ == '__main__':
    result = load_spec(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False))
