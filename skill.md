---
name: qa-checker
description: 이벤트 로그 CSV를 YAML 스펙과 대조해 QA 검증 후 Slack 발송. 스펙 동기화(구글 시트 → YAML git commit)도 지원합니다.
---

# QA Checker

이벤트 로그 CSV를 YAML 스펙과 비교해 프로퍼티명·타입·필수값·허용값을 검증하고, 결과를 Slack으로 알립니다.
스펙 동기화 요청 시 구글 시트 → YAML 파일 갱신 → git commit을 자동 처리합니다.

---

## 패밀리 주문 시나리오 검증 모드

사용자가 `type: family_order`인 시나리오를 요청하면 아래 절차를 실행한다.

### FO1. 설정 및 CSV 확인

```bash
cat ~/.qa-checker/config.yaml
```

`braze.api_key`, `braze.server`, `slack.bot_token`, `slack.channel`을 읽는다. CSV 경로를 확인한다.

### FO2. 파싱 및 검증 실행

```bash
python3 {repo_path}/scripts/parse_csv.py {csv_path}
python3 {repo_path}/scripts/load_spec.py {repo_path}/specs/
python3 {repo_path}/scripts/validate_family_order.py '{rows}' '{spec}' '{scenario_name}' '{repo_path}/specs' '{braze_api_key}' '{braze_server}'
```

### FO3. 결과 보고 및 Slack 발송

결과는 order_no별로 멤버/리더 구분해서 리포트한다:
- 수집된 이벤트 목록
- 미수집 이벤트
- 프로퍼티 위반 (스펙 YAML 참조)
- 어트리뷰트 불일치
- cross_check 불일치

```bash
python3 {repo_path}/scripts/slack_notify_family_order.py '{results}' '{filename}' '{bot_token}' '{channel}'
```

---

## 시나리오 검증 모드

사용자가 `/qa-checker {시나리오명} 검증` 또는 `/qa-checker {시나리오명} 시나리오 검증` 형식으로 요청하면 아래 절차를 실행한다.

### SC1. 설정 및 CSV 확인

```bash
cat ~/.qa-checker/config.yaml
```

CSV 경로를 사용자에게 확인한다.

### SC2. 파싱 및 시나리오 검증 실행

```bash
python3 {repo_path}/scripts/parse_csv.py {csv_path}
python3 {repo_path}/scripts/load_spec.py {repo_path}/specs/
python3 {repo_path}/scripts/validate_scenario.py '{rows}' '{spec}' '{scenario_name}' '{repo_path}/specs'
```

시나리오에 `attribute_checks`가 있으면 어트리뷰트 검증도 실행한다:

```bash
python3 {repo_path}/scripts/validate_attributes.py '{rows}' '{repo_path}/specs' '{scenario_name}' '{braze_api_key}' '{braze_server}'
```

`attribute_checks`가 없는 시나리오면 생략한다. 결과가 있으면 `results`에 `attribute_violations` 키로 병합한다.

### SC3. 결과 보고 및 Slack 발송

결과에서 다음을 요약한다:
- `missing_events`: 미수집 이벤트 목록
- `skipped_conditional`: 조건부 수집으로 제외된 이벤트 목록
- `violations`: 포맷 위반 목록
- `attribute_violations`: 어트리뷰트 불일치 목록 (있는 경우)

```bash
python3 {repo_path}/scripts/slack_notify.py '{results}' '[]' '{filename}' '{bot_token}' '{channel}'
```

---

## 어트리뷰트 QA 모드

사용자가 "어트리뷰트 QA", "어트리뷰트 검증" 등을 요청하면 아래 절차를 실행한다.

### AT1. 설정 및 CSV 확인

```bash
cat ~/.qa-checker/config.yaml
```

`braze.api_key`와 `braze.server`를 읽는다. CSV 경로를 사용자에게 확인한다.

### AT2. CSV 파싱 및 어트리뷰트 검증 실행

```bash
python3 {repo_path}/scripts/parse_csv.py {csv_path}
python3 {repo_path}/scripts/validate_attributes.py '{rows}' '{repo_path}/specs' '{scenario_name}' '{api_key}' '{server}'
```

### AT3. 결과 보고 및 Slack 발송

결과에서 다음을 요약한다:
- `violations`: 어트리뷰트 불일치 목록 (user_id, event, key, expected, actual)
- `total_checked`: 검증된 유저 수

```bash
python3 {repo_path}/scripts/slack_notify_attributes.py '{results}' '{filename}' '{bot_token}' '{channel}'
```

---

## 스펙 동기화 모드

사용자가 "스펙 동기화", "sync", "시트 반영", "yaml → 시트", "yaml을 시트에 반영" 등을 요청하면 **QA 검증 대신** 아래 절차를 실행한다.

요청이 **시트 → YAML** 방향이면 S1~S3을 실행한다.
요청이 **YAML → 시트** 방향이면 S4를 실행한다. 방향이 명시되지 않으면 사용자에게 확인한다.

### S1. 설정 읽기

```bash
cat ~/.qa-checker/config.yaml
```

`repo_path`와 `sheet.specs_url`을 읽는다.
`sheet.specs_url`이 없으면:
> `config.yaml`에 `sheet.specs_url`이 없습니다. `config.yaml.example`을 참고해 추가해 주세요.

### S2. 동기화 실행

```bash
python3 {repo_path}/scripts/sync_specs.py "{specs_url}" {repo_path}/specs {repo_path}
```

### S3. 결과 보고

- 변경된 이벤트 목록을 보여준다.
- 변경사항이 있으면 팀원 반영을 위해 `git push` 여부를 묻는다.
- 사용자가 동의하면: `git push origin main` (cwd: repo_path)

### S4. YAML → 시트 동기화

`sheet.sheet_id`, `sheet.tab_name`, `sheet.service_account`를 config에서 읽는다.

```bash
python3 {repo_path}/scripts/sync_yaml_to_sheet.py {repo_path}/specs {sheet_id} "{tab_name}" {service_account_path}
```

완료 후 업데이트된 행 수를 보고한다.

---

## QA 검증 모드

## 실행 절차

### 1. 설정 파일 읽기

아래 명령으로 설정을 읽는다:

```bash
cat ~/.qa-checker/config.yaml
```

`repo_path`와 `slack.webhook_url`을 읽는다. 파일이 없으면 사용자에게 안내한다:
> `~/.qa-checker/config.yaml`이 없습니다. `config.yaml.example`을 참고해 생성해 주세요.

### 2. CSV 파일 경로 확인

사용자에게 CSV 파일 경로를 묻는다. 경로가 제공되지 않은 경우에만 질문한다.

### 3. CSV 파싱

```bash
python3 {repo_path}/scripts/parse_csv.py {csv_path}
```

출력(JSON)을 `rows` 변수에 저장한다.

### 4. 스펙 로드

```bash
python3 {repo_path}/scripts/load_spec.py {repo_path}/specs
```

출력(JSON)을 `spec` 변수에 저장한다.

### 5. 검증 실행

사용자가 "제외 이벤트"를 명시한 경우 해당 이벤트명을 JSON 배열로 넘긴다:

```bash
python3 {repo_path}/scripts/validate.py '{rows}' '{spec}' '{skip_events_json}'
```

제외 이벤트가 없으면:

```bash
python3 {repo_path}/scripts/validate.py '{rows}' '{spec}'
```

출력(JSON)에서 `violations`, `unknowns`, `total_rows`를 읽는다.

### 6. 미정의 항목 AI 추론

`unknowns` 목록의 각 항목에 대해 `sample_values`를 분석해 아래를 추론한다:
- `inferred_type`: `string`, `boolean`, `integer`, `number`, `datetime` 중 하나
- `inferred_required`: `true` / `false`

기존 스펙의 유사 프로퍼티 패턴을 참고해 추론한다.
결과를 `inference` 배열로 구성한다:

```json
[
  {
    "event_name": "pdp_view",
    "key": "new_prop",
    "inferred_type": "string",
    "inferred_required": false
  }
]
```

### 7. Slack 발송

`bot_token`과 `channel`을 config에서 읽어 실행한다:

```bash
python3 {repo_path}/scripts/slack_notify.py '{results}' '{inference}' '{filename}' '{bot_token}' '{channel}'
```

여기서 `{filename}`은 CSV 파일명(경로 제외), `{results}`는 Step 5의 출력 JSON이다.
첫 메시지로 `[날짜 QA 결과]` 요약을 보내고, 상세 내용은 스레드 댓글로 달린다.
