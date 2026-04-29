---
name: qa-checker
description: 이벤트 로그 CSV를 YAML 스펙과 대조해 QA 검증 후 Slack 발송. 스펙 동기화(구글 시트 → YAML git commit)도 지원합니다.
---

# QA Checker

이벤트 로그 CSV를 YAML 스펙과 비교해 프로퍼티명·타입·필수값·허용값을 검증하고, 결과를 Slack으로 알립니다.

---

## 온보딩 모드

사용자가 레포 링크를 붙여넣고 "설치해줘", "시작", "세팅", "처음 설정" 등을 요청하거나,
`~/.qa-checker/config.yaml`이 없거나 `specs/` 디렉토리에 YAML 파일이 없으면
아래 안내문을 먼저 출력한 뒤 3단계를 순서대로 진행한다.
**각 단계는 사용자 확인 후 다음 단계로 넘어간다.**

---

아래 안내문을 출력한다:

> ## QA Checker에 오신 걸 환영해요!
>
> 이 도구는 **수집한 데이터가 스펙대로 제대로 수집되고 있는지 자동으로 확인**해 주고, 결과를 Slack으로 바로 쏴줍니다.
>
> 크게 세 가지를 할 수 있어요:
>
> **① 전체 QA** — 이벤트 로그 전체를 스펙이랑 비교해요.
> 예를 들어 `pdp_view` 이벤트에 `product_no`가 빠져있거나, 타입이 다르거나, 허용되지 않은 값이 들어왔을 때 딱 잡아냅니다.
>
> **② 시나리오 검증** — 특정 사용자 흐름에서 이벤트가 순서대로 다 발생했는지 봐요.
> 예를 들어 "장바구니 담기" 시나리오면 `add_to_cart → order → order_complete`가 다 수집됐는지, 각 프로퍼티가 올바른지 한 번에 확인합니다.
>
> **③ 어트리뷰트 QA** — 이벤트가 발생한 뒤 유저 어트리뷰트가 제대로 바뀌었는지 체크해요.
> 예를 들어 `push_subscribe` 이벤트 후 Braze에서 `is_push_subscribed`가 `true`로 업데이트됐는지 확인합니다.
>
> ---
>
> 총 3단계로 진행할게요. 각 단계 끝나면 확인하고 다음으로 넘어갑니다.
>
> **1단계 — 기본 설정** (약 5분)
> Slack이랑 Braze 연동, 구글 시트 연결까지 마무리할게요.
>
> **2단계 — 이벤트 스펙 등록** (약 10분)
> 갖고 계신 이벤트 택소노미를 스펙으로 변환해서 구글 시트에 등록할게요.
> 이후엔 시트만 관리하면 자동으로 반영됩니다.
>
> **3단계 — 시운영** (약 5분)
> Braze에서 이벤트 로그 뽑아서 첫 번째 검증 같이 돌려볼게요.
>
> 그럼 시작할게요!

---

### 1단계. 기본 설정

#### 1-1. config 파일 확인

```bash
cat ~/.qa-checker/config.yaml
```

파일이 없으면 아래를 출력한 뒤 항목을 하나씩 수집한다:

> **설정 파일을 같이 만들어볼게요!**
>
> QA 결과는 Slack으로 바로 오게 돼요. 아래 정보를 하나씩 알려주세요.
>
> 1. **레포 절대 경로**
>    터미널에서 `pwd` 입력하면 바로 나와요.
>    예: `/Users/your-name/Projects/qa-checker`
>
> 2. **Slack Bot Token**
>    `xoxb-...` 형식이에요.
>    Slack 앱 관리 페이지 → 해당 앱 → OAuth & Permissions → Bot User OAuth Token에서 확인할 수 있어요.
>
> 3. **Slack 채널명**
>    QA 결과 받을 채널 이름이요. 예: `qa-alerts`
>
> 4. **Slack 채널 ID**
>    채널명 옆 `···` → 채널 세부정보 보기 → 맨 아래에 `C`로 시작하는 값이에요.

수집 완료 후:

> **Braze 연동 정보를 알려주세요.**
> 이벤트 발생 후 유저 어트리뷰트가 올바르게 업데이트됐는지 확인할 때 사용됩니다.
>
> - Braze REST API Key
> - Braze 서버 주소 (예: `rest.iad-01`)
>
> API Key는 `~/.qa-checker/config.yaml`에 저장됩니다.
> 이 파일은 내 컴퓨터 로컬에만 존재하고, git에는 올라가지 않아서 외부에 노출될 걱정은 없어요.

수집한 값으로 `~/.qa-checker/config.yaml`을 생성한다.

#### 1-2. 스펙 시트 연동

> **이제 스펙을 기록할 구글 시트를 연결할게요.**
>
> 이 시트가 앞으로 스펙의 공식 원본이 돼요.
> 시트 수정하면 스펙에 자동 반영되고, 반대로도 동기화됩니다.
>
> 일단 **비어있는 구글 스프레드시트를 하나 새로 만들어 주세요.**
> 다 만드셨으면 URL 공유해 주시면 돼요!

시트 URL을 받으면 sheet_id와 tab_name을 추출해 config에 저장한다.

그 다음 연동 방식을 선택하게 한다:

> **시트 연동 방식 두 가지 중 하나를 골라주세요.**
>
> **A. 공개 링크 방식 (일단 빠르게 시작하고 싶다면)**
> - 시트 오른쪽 상단 [공유] → "링크 있는 사람 누구나" → **뷰어**로 설정하면 끝
> - 시트 → 스펙 방향만 동기화돼요. 스펙 수정 내용이 시트로 자동 반영되진 않아요.
>
> **B. 서비스 계정 방식 (권장 — 양방향 동기화)**
> - 시트 읽기/쓰기가 다 돼서 항상 양방향으로 맞춰줘요.
> - 설정이 조금 있는데 같이 진행해볼게요:
>   1. [Google Cloud Console](https://console.cloud.google.com) 접속
>   2. 왼쪽 메뉴 → API 및 서비스 → 사용자 인증 정보 → 서비스 계정 만들기
>   3. 만들어진 서비스 계정 클릭 → 키 탭 → 키 추가 → JSON 다운로드
>   4. 다운로드된 파일을 `~/.qa-checker/service_account.json`으로 저장
>   5. 시트 [공유]에서 서비스 계정 이메일을 **편집자**로 추가
>
> 어떤 걸로 할까요?

선택에 따라 config에 `sheet` 항목을 추가한다.

> **1단계 완료!** 설정 저장됐어요. 2단계로 넘어갈까요?

---

### 2단계. 이벤트 스펙 등록

> **이제 스펙 시트를 채울게요.**
>
> 스펙 시트는 "어떤 이벤트에 어떤 프로퍼티가 있어야 하는지"를 적어두는 문서예요.
> 이걸 기준으로 실제 로그랑 비교해서 문제를 찾아냅니다.
>
> 방금 만드신 시트 1행에 아래 헤더를 추가해 주세요:
>
> | 이벤트 명 | 프로퍼티명 | 데이터 타입 | 필수 여부 | 내용 조건 |
> |---------|-----------|-----------|---------|---------|
>
> 각 컬럼이 어떤 의미인지 간단히 설명할게요:
> - **이벤트 명**: 이벤트 이름이에요. 예: `pdp_view`, `add_to_cart`
> - **프로퍼티명**: 프로퍼티 key예요. 예: `product_no`, `screen_name`
> - **데이터 타입**: `string` / `boolean` / `integer` / `number` / `time` 중 하나
> - **필수 여부**: `Y`(무조건 있어야 함) / `N`(없어도 됨) / `CONDITIONAL`(조건부라 검증 제외)
> - **내용 조건**: 허용값이나 패턴 있을 때만 입력, 없으면 그냥 비워두세요
>   - 허용값 예: `enum: iOS, Android, web`
>   - 패턴 예: `regex: ^\d+$`
>
> 헤더 추가하셨으면, 이번엔 **이벤트 택소노미 문서를 공유해 주세요.**
> 구글 시트, 엑셀, 노션 링크 등 갖고 계신 형식 뭐든 괜찮아요.
> 읽어서 스펙 시트 형식으로 변환한 다음 내용을 채워드릴게요!

#### 2-1. 택소노미 구조 파악

공유받은 파일/URL에서 데이터를 읽는다. 구글 시트인 경우:

```bash
curl -sL "{csv_export_url}" | head -10
```

읽은 데이터의 구조 유형을 판단한다:

**유형 A — 행 = 프로퍼티**: 한 행에 이벤트명 + 프로퍼티명이 함께 있는 형태
예: `이벤트명 | 프로퍼티명 | 타입 | 필수 여부 | 설명`

**유형 B — 그 외 구조**: 이벤트 1행에 프로퍼티가 여러 열로 나열되거나, 설명 문서 형태

#### 2-2. 스펙 변환 및 미리보기

**유형 A**: 컬럼 매핑을 감지해 사용자에게 확인한다.

> 시트에서 컬럼을 읽어봤는데요, 이렇게 매핑하면 될 것 같아요. 맞나요?
>
> | 항목 | 감지된 컬럼 |
> |------|-----------|
> | 이벤트명 | `{감지 결과}` |
> | 프로퍼티명 | `{감지 결과}` |
> | 데이터 타입 | `{감지 결과}` |
> | 필수 여부 | `{감지 결과}` |
> | 값 조건 | `{감지 결과}` |
>
> 다르게 매핑해야 할 컬럼이 있으면 말씀해 주세요!

매핑 확정 후 config의 `column_map`에 저장한다.

**유형 B**: Claude가 직접 구조를 해석해 스펙을 생성한다. 타입과 필수 여부는 컬럼명·설명·예시값을 보고 추론한다.

변환 결과를 표로 미리 보여준다 (최대 20행):

> 변환 결과예요! 한번 확인해 주세요:
>
> | 이벤트명 | 프로퍼티명 | 타입 | 필수 | 값 조건 |
> |---------|-----------|------|-----|--------|
> | ...     | ...       | ...  | ... | ...    |
>
> 괜찮으면 **"승인"**이라고 해주세요. 수정할 부분이 있으면 어떤 게 잘못됐는지 알려주시면 고칠게요.

#### 2-3. 스펙 저장 (승인 후 실행)

**유형 A**:
```bash
python3 {repo_path}/scripts/sync_specs.py "{specs_url}" {repo_path}/specs {repo_path}
```

**유형 B**: Claude가 생성한 YAML을 `specs/{이벤트명}.yaml`로 저장 후 commit한다.
```bash
git -C {repo_path} add specs/
git -C {repo_path} commit -m "chore: init specs from event taxonomy"
```

#### 2-4. 스펙 시트 동기화

> 변환된 스펙을 구글 시트에도 반영합니다.
> 이렇게 하면 앞으로 시트가 스펙의 공식 원본이 됩니다 —
> 시트를 수정하면 스펙에 자동 반영되고, 스펙을 수정하면 시트에 자동 업데이트됩니다.

서비스 계정이 설정된 경우:
```bash
python3 {repo_path}/scripts/sync_yaml_to_sheet.py {repo_path}/specs {sheet_id} "{tab_name}" {service_account_path}
```

서비스 계정이 없는 경우:
> 공개 링크 방식이라 시트 자동 업데이트는 건너뛸게요.
> 나중에 서비스 계정 설정하면 `yaml을 시트에 반영해줘`로 언제든 동기화할 수 있어요.

완료 후 스펙을 팀원과 공유하기 위해 PR 생성 여부를 묻는다:

> 스펙 파일 팀원들한테 공유하려면 PR을 만들어야 해요.
> 팀장이 확인하고 승인하면 팀 전체에 반영됩니다. PR 만들까요?

PR 생성에 동의하면:
```bash
git -C {repo_path} checkout -b sync/init-specs
git -C {repo_path} push origin sync/init-specs
gh pr create --repo {repo} --base main --head sync/init-specs \
  --title "chore: 이벤트 스펙 초기 등록" \
  --body "이벤트 택소노미를 기반으로 QA 스펙을 초기 등록합니다."
```

> **2단계 완료!** 스펙 등록됐어요. 마지막으로 실제 로그로 한 번 돌려볼게요!

---

### 3단계. 이벤트 로그 연동 및 시운영

> **거의 다 왔어요! 실제 이벤트 로그로 검증 한 번만 돌려보면 끝이에요.**
>
> Braze Query Builder에서 아래 쿼리로 이벤트 로그를 뽑아주세요.
> `user_id`랑 날짜 조건만 본인 상황에 맞게 바꾸면 돼요.
>
> ```sql
> SELECT
>     id AS event_id,
>     user_id,
>     CONVERT_TIMEZONE('UTC', 'Asia/Seoul', TO_TIMESTAMP(time)) AS time,
>     name,
>     properties
> FROM USERS_BEHAVIORS_CUSTOMEVENT_SHARED
> WHERE user_id = '검증할_유저_ID'
> AND CONVERT_TIMEZONE('UTC', 'Asia/Seoul', TO_TIMESTAMP(time))::DATE >= '2024-01-01'
> ORDER BY time DESC
> ```
>
> 쿼리 실행 후 결과를 CSV로 내보내기 하고, 파일 경로 알려주세요!

#### 3-2. 시운영 실행

사용자가 CSV를 준비하면:

```bash
cat ~/.qa-checker/config.yaml
python3 {repo_path}/scripts/parse_csv.py {csv_path}
python3 {repo_path}/scripts/load_spec.py {repo_path}/specs
python3 {repo_path}/scripts/validate.py '{rows}' '{spec}'
```

검증 결과를 요약해서 보여준다. Slack 발송 여부를 묻는다.

Slack 발송 후 아래를 출력한다:

> **첫 QA 자동화 사용을 축하드려요! 🎉**
>
> 앞으로 이렇게 쓰시면 돼요:
> 이벤트 CSV 다운로드 후
> - `QA 해줘` → 이벤트 로그 전체 검증
> - `스펙 동기화해줘` → 시트 변경사항 스펙에 반영
>
> 한 가지 더 — **시나리오 검증**도 설정할 수 있어요.
>
> 특정 사용자 흐름(예: 결제 완료 시나리오, 멤버십 가입 흐름)에서 이벤트가 순서대로 다 발생했는지, 이벤트 간 프로퍼티 값이 일치하는지까지 한 번에 검증하는 기능이에요.
>
> 4단계로 넘어갈까요, 아니면 나중에 필요할 때 설정할까요?

사용자가 진행을 원하면 4단계로 넘어간다. 원하지 않으면 온보딩을 마친다.

---

### 4단계. 시나리오 등록 (선택)

> **시나리오 검증은 특정 사용자 흐름 전체를 한 번에 검증하는 기능이에요.**
>
> 예를 들어 이런 경우에 유용해요:
>
> - **멤버십 가입 시나리오** — 가입 이벤트 발생 후 Braze 어트리뷰트가 올바르게 업데이트됐는지까지 한 번에 확인
> - **결제 완료 시나리오** — 결제 요청 → 결제 완료 흐름에서 각 단계 이벤트가 다 수집됐는지, 프로퍼티 값이 일치하는지 한 번에 검증
>
> 단순히 이벤트 프로퍼티만 체크하는 수준이라면 굳이 설정 안 해도 돼요.
> 여러 이벤트가 순서대로 발생해야 하거나, 유저 간 데이터가 연결되는 흐름이 있을 때 특히 유용합니다.
>
> 어떤 시나리오를 설정하고 싶으신가요? 흐름을 설명해 주시면 YAML로 만들어드릴게요.

#### 4-1. 시나리오 구성 파악

사용자가 설명한 흐름을 바탕으로 아래 항목을 파악한다:

- **시나리오 이름**: 어떤 흐름인지 (예: 결제 완료, 멤버십 가입)
- **필수 이벤트 목록**: 반드시 발생해야 하는 이벤트
- **선택 이벤트 목록**: 발생할 수도 있는 이벤트 (예: 취소, 환불)
- **어트리뷰트 체크**: 이벤트 후 Braze 어트리뷰트가 바뀌는 게 있는지
- **멀티 유저 여부**: 리더/멤버처럼 여러 유저 간 데이터가 연결되는지

불명확한 부분은 사용자에게 확인한다.

#### 4-2. 시나리오 YAML 생성 및 미리보기

파악한 내용으로 `specs/scenarios/{시나리오명}.yaml`을 생성한다.

변환 결과를 보여주고 확인을 받는다:

> 이렇게 만들면 될 것 같아요. 맞는지 확인해 주세요!
>
> ```yaml
> name: {시나리오명}
> events:
>   - name: {이벤트명}
>     required: true
>   ...
> ```
>
> 괜찮으면 **"승인"**, 수정할 부분 있으면 알려주세요.

#### 4-3. 저장 및 PR 생성

승인 후 파일을 저장하고 PR을 생성한다.

```bash
git -C {repo_path} checkout -b sync/add-scenario-{시나리오명}
git -C {repo_path} add specs/scenarios/
git -C {repo_path} commit -m "feat: {시나리오명} 시나리오 추가"
git -C {repo_path} push origin sync/add-scenario-{시나리오명}
gh pr create --repo {repo} --base main --head sync/add-scenario-{시나리오명} \
  --title "feat: {시나리오명} 시나리오 추가" \
  --body "{시나리오명} 시나리오 검증을 위한 YAML 파일을 추가합니다."
```

> **설치 완료! 이제 다 됐어요 🎉**
>
> 앞으로 이렇게 쓰시면 돼요:
> - `QA 해줘` → 이벤트 로그 전체 검증
> - `{시나리오명} 검증해줘` → 방금 등록한 시나리오 검증
> - `스펙 동기화해줘` → 시트 변경사항 스펙에 반영

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

### 1. 설정 파일 읽기

```bash
cat ~/.qa-checker/config.yaml
```

`repo_path`와 `slack.bot_token`을 읽는다. 파일이 없으면:
> `~/.qa-checker/config.yaml`이 없습니다. `설치 완료`라고 말씀해 주세요.

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

