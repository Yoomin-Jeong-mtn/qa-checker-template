import csv
import json
import sys
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def parse_csv(filepath: str, date_filter=None) -> list[dict]:
    rows = []
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):
            time_str = row['TIME']
            if date_filter and not time_str.startswith(date_filter):
                continue
            rows.append({
                'row': i,
                'name': row['NAME'],
                'time': time_str,
                'user_id': row['USER_ID'],
                'event_id': row['EVENT_ID'],
                'properties': json.loads(row['PROPERTIES']),
            })
    return rows


if __name__ == '__main__':
    filepath = sys.argv[1]
    date_filter = None
    if '--today' in sys.argv:
        date_filter = datetime.now(KST).strftime('%Y-%m-%d')
    elif '--date' in sys.argv:
        idx = sys.argv.index('--date')
        date_filter = sys.argv[idx + 1]
    result = parse_csv(filepath, date_filter)
    print(json.dumps(result, ensure_ascii=False))
