import json
import sys
from datetime import datetime

import requests

SLACK_MAX_CHARS = 3000
SLACK_API = 'https://slack.com/api'


def format_summary(results: dict, filename: str) -> str:
    violations = results.get('violations', [])
    total = results.get('total_rows', 0)
    missing = results.get('missing_events', [])
    scenario = results.get('scenario', '')

    attr_violations = results.get('attribute_violations', [])

    now = datetime.now()
    today = f"{now.month}.{now.day}"
    has_issue = bool(violations or missing or attr_violations)
    status = '⚠️ 이슈 있음' if has_issue else '✅ 이상 없음'

    title = f"[{today} QA 결과]"
    status_line = status
    if scenario:
        status_line += f" | {scenario}"

    if missing:
        stats_line = f"총 {total}행  검증 : 미수집 {len(missing)}건  |  포맷 위반 {len(violations)}건  |  어트리뷰트 {len(attr_violations)}건"
    else:
        violated_ids = {v['event_id'] for v in violations}
        passed = total - len(violated_ids)
        stats_line = f"총 {total}행  검증 : 정상 {passed}건  |  위반 {len(violations)}건  |  어트리뷰트 {len(attr_violations)}건"

    return f"{title}\n{status_line}\n{stats_line}"


def format_detail_chunks(results: dict, inference: list) -> list[str]:
    violations = results.get('violations', [])
    missing = results.get('missing_events', [])
    skipped = results.get('skipped_conditional', [])
    attr_violations = results.get('attribute_violations', [])

    lines = []

    if missing or skipped:
        total_missing = len(missing) + len(skipped)
        lines.append(f"📋 미수집 이벤트 ({total_missing}개)")
        for e in missing:
            lines.append(f"  • {e}")
        if skipped:
            lines.append(f"  • 조건부 미수집")
            for e in skipped:
                lines.append(f"      • {e}")
    else:
        lines.append("📋 미수집 이벤트: 없음")

    lines.append("")

    if violations:
        lines.append(f"❌ 포맷 위반 ({len(violations)}건)")
        for v in violations:
            event_name = v.get('event_name', '')
            event_id = v.get('event_id', '')
            lines.append(f"  • {event_name}${v['key']}: {v['error_detail']}")
            lines.append(f"      • event_id: {event_id}")
    else:
        lines.append("❌ 포맷 위반: 없음")

    lines.append("")

    if attr_violations:
        lines.append(f"🔗 어트리뷰트 불일치 ({len(attr_violations)}건)")
        for v in attr_violations:
            if v.get('key'):
                lines.append(f"  • [{v['event']}] {v['key']}: {v['error']}")
            else:
                lines.append(f"  • [{v['event']}] {v['error']}")
            lines.append(f"      • user_id: {v['user_id']}")
    else:
        lines.append("🔗 어트리뷰트 불일치: 없음")

    lines.append("")

    if inference:
        lines.append(f"🔍 미정의 프로퍼티 — AI 추론 ({len(inference)}건)")
        for item in inference:
            lines.append(f"  • [{item['event_name']}] {item['key']}")
            lines.append(f"      • 추론: {item['inferred_type']}, required: {item['inferred_required']}")
    else:
        lines.append("🔍 미정의 프로퍼티: 없음")

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


def post_message(token: str, channel: str, text: str, thread_ts: str = None) -> str:
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


def send_to_slack(token: str, channel: str, results: dict, inference: list, filename: str) -> None:
    # 1. 스레드 부모 메시지 (요약)
    summary = format_summary(results, filename)
    thread_ts = post_message(token, channel, summary)

    # 2. 상세 내용을 스레드 댓글로
    chunks = format_detail_chunks(results, inference)
    for chunk in chunks:
        post_message(token, channel, chunk, thread_ts=thread_ts)

    print(f"Slack 알림 발송 완료 (스레드 댓글 {len(chunks)}개)")


if __name__ == '__main__':
    results = json.loads(sys.argv[1])
    inference = json.loads(sys.argv[2])
    filename = sys.argv[3]
    token = sys.argv[4]
    channel = sys.argv[5]
    send_to_slack(token, channel, results, inference, filename)
