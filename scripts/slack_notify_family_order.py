"""패밀리 주문 시나리오 QA 결과 Slack 발송"""
import json
import sys
from datetime import datetime

import requests

SLACK_MAX_CHARS = 3000
SLACK_API = 'https://slack.com/api'

PHASE_LABELS = {
    'request': '결제 요청',
    'complete': '결제 완료',
    'reject': '요청 거절',
    'cancel_after_complete': '결제 후 취소',
}


def format_summary(results, filename):
    now = datetime.now()
    today = f"{now.month}.{now.day}"

    total_orders = len(results)
    has_issue = any(
        r['member']['missing_events'] or r['member']['violations'] or r['member']['attribute_violations']
        or r['leader']['missing_events'] or r['leader']['violations']
        or r['leader']['cross_check_violations'] or r['leader']['attribute_violations']
        for r in results
    )
    status = '⚠️ 이슈 있음' if has_issue else '✅ 이상 없음'

    return f"[{today} 패밀리 결제 QA 결과]\n{status}\n총 {total_orders}건 주문 검증"


def format_order_block(order):
    order_no = order['order_no']
    phase = PHASE_LABELS.get(order['phase'], order['phase'])
    lines = [f"📦 order_no: {order_no}  |  단계: {phase}"]

    for role_key, role_label, icon in [('member', '멤버', '👤'), ('leader', '리더', '👑')]:
        role = order[role_key]
        uid = role.get('user_id', '-')
        lines.append(f"\n{icon} {role_label} (user_id: {uid})")

        # 수집 이벤트
        for e in role.get('events', []):
            lines.append(f"  ✅ {e}")

        # 미수집 이벤트
        for e in role.get('missing_events', []):
            lines.append(f"  ❌ {e}: 미수집")

        # 프로퍼티 위반
        for v in role.get('violations', []):
            spec_hint = f"  ({v['spec']})" if v.get('spec') else ''
            if v.get('event_id'):
                lines.append(f"  ⚠️ {v['event']}${v['key']}: {v['error']}{spec_hint}")
                lines.append(f"      • event_id: {v['event_id']}")
            else:
                lines.append(f"  ⚠️ {v.get('event', '')}${v.get('key', '')}: {v['error']}{spec_hint}")

        # 어트리뷰트 위반
        for v in role.get('attribute_violations', []):
            lines.append(f"  🔗 {v['key']}: {v['error']}")

        # cross_check 위반 (리더만)
        for v in role.get('cross_check_violations', []):
            lines.append(f"  🔀 {v['event']}${v['key']}: {v['error']}")

    return "\n".join(lines)


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

    full_text = "\n\n".join(format_order_block(r) for r in results)
    chunks = []
    while len(full_text) > SLACK_MAX_CHARS:
        split_at = full_text.rfind('\n', 0, SLACK_MAX_CHARS)
        if split_at == -1:
            split_at = SLACK_MAX_CHARS
        chunks.append(full_text[:split_at])
        full_text = full_text[split_at:]
    chunks.append(full_text)

    for chunk in chunks:
        post_message(token, channel, chunk, thread_ts=thread_ts)

    print(f"Slack 알림 발송 완료 (스레드 댓글 {len(chunks)}개)")


if __name__ == '__main__':
    results = json.loads(sys.argv[1])
    filename = sys.argv[2]
    token = sys.argv[3]
    channel = sys.argv[4]
    send_to_slack(token, channel, results, filename)
