"""어트리뷰트 QA 결과 Slack 발송"""
import json
import sys
from datetime import datetime

import requests

SLACK_MAX_CHARS = 3000
SLACK_API = 'https://slack.com/api'


def format_summary(results, filename):
    violations = results.get('violations', [])
    total = results.get('total_checked', 0)

    now = datetime.now()
    today = f"{now.month}.{now.day}"
    status = '⚠️ 이슈 있음' if violations else '✅ 이상 없음'

    return (
        f"[{today} 어트리뷰트 QA 결과]\n"
        f"{status}\n"
        f"총 {total}명 검증 : 불일치 {len(violations)}건"
    )


def format_detail_chunks(results):
    violations = results.get('violations', [])
    lines = []

    if violations:
        lines.append(f"❌ 어트리뷰트 불일치 ({len(violations)}건)")
        for v in violations:
            if v.get('key'):
                lines.append(f"  • [{v['event']}] {v['key']}: {v['error']}")
                lines.append(f"      • user_id: {v['user_id']}")
            else:
                lines.append(f"  • [{v['event']}] {v['error']}")
                lines.append(f"      • user_id: {v['user_id']}")
    else:
        lines.append("❌ 어트리뷰트 불일치: 없음")

    full_text = "\n".join(lines)
    chunks = []
    while len(full_text) > SLACK_MAX_CHARS:
        split_at = full_text.rfind('\n', 0, SLACK_MAX_CHARS)
        if split_at == -1:
            split_at = SLACK_MAX_CHARS
        chunks.append(full_text[:split_at])
        full_text = full_text[split_at:]
    chunks.append(full_text)
    return chunks


def post_message(token, channel, text, thread_ts=None):
    payload = {'channel': channel, 'text': text}
    if thread_ts:
        payload['thread_ts'] = thread_ts
    resp = requests.post(
        f'{SLACK_API}/chat.postMessage',
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json; charset=utf-8'},
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get('ok'):
        raise RuntimeError(f"Slack error: {data.get('error')}")
    return data['ts']


def send_to_slack(token, channel, results, filename):
    summary = format_summary(results, filename)
    thread_ts = post_message(token, channel, summary)

    chunks = format_detail_chunks(results)
    for chunk in chunks:
        post_message(token, channel, chunk, thread_ts=thread_ts)

    print(f"Slack 알림 발송 완료 (스레드 댓글 {len(chunks)}개)")


if __name__ == '__main__':
    results = json.loads(sys.argv[1])
    filename = sys.argv[2]
    token = sys.argv[3]
    channel = sys.argv[4]
    send_to_slack(token, channel, results, filename)
