# QA Checker

이벤트 로그 CSV를 스펙과 비교해 프로퍼티명·타입·필수값·허용값을 검증하고, 결과를 Slack으로 알립니다.

스펙은 **구글 시트**에서 관리하며, YAML로 자동 변환됩니다. YAML을 직접 수정한 경우 시트로 역동기화할 수 있습니다.

---

## 전체 흐름

```
구글 시트 (스펙 원본)
      ↕  시트 → YAML (sync_specs.py)
      ↕  YAML → 시트 (sync_yaml_to_sheet.py)
  YAML 파일 (검증 소스)
      ↓
  QA 검증 (이벤트 로그 CSV vs YAML)
      ↓
  Slack 결과 발송
```

---

## 시작하기

### 1. 레포 클론 및 패키지 설치

```bash
git clone https://github.com/YOUR_ORG/qa-checker-template.git
cd qa-checker-template
pip3 install -r requirements.txt
```

### 2. 설정 파일 생성

```bash
cp config.yaml.example ~/.qa-checker/config.yaml
```

`~/.qa-checker/config.yaml`을 열어 항목을 채워주세요:

| 항목 | 설명 |
|------|------|
| `repo_path` | 이 레포를 클론한 절대 경로 |
| `slack.bot_token` | Slack Bot Token (`xoxb-...`) |
| `slack.channel` | 결과를 발송할 Slack 채널명 |
| `slack.channel_id` | 채널 ID |
| `braze.api_key` | Braze REST API Key (어트리뷰트 QA 시 필요) |
| `braze.server` | Braze 서버 (예: `rest.iad-01`) |
| `sheet.specs_url` | 시트 CSV export URL (시트→YAML 동기화용) |
| `sheet.sheet_id` | 구글 시트 ID (YAML→시트 동기화용) |
| `sheet.tab_name` | 시트 탭 이름 |
| `sheet.service_account` | 서비스 계정 JSON 경로 |

### 3. 구글 시트 준비

스펙 시트에 아래 컬럼이 있어야 합니다:

| 이벤트 명 | 프로퍼티명 | 데이터 타입 | 필수 여부 | 내용 조건 |
|-----------|-----------|-------------|-----------|-----------|
| pdp_view | product_no | string | Y | |
| pdp_view | screen_name | string | Y | enum: home, pdp, cart |
| pdp_view | item_count | integer | N | |
| pdp_view | created_at | time | Y | |

**데이터 타입** 허용값: `string`, `boolean`, `number`, `integer`, `time`

**필수 여부** 허용값:
- `Y` — 필수 (값 없으면 오류)
- `N` — 선택 (빈값 허용)
- `CONDITIONAL` — 조건부 수집 (검증 제외)

**내용 조건** 예시:
- `enum: active, inactive` — 허용값 목록
- `regex: ^\d+$` — 정규식 패턴
- `if_contains(키워드1 / 키워드2) → must_match: 패턴` — 조건부 패턴

> 시트는 **"링크 있는 사람 누구나 보기"** 권한으로 설정하거나, 서비스 계정 이메일을 공유해야 합니다.

### 4. 시트 → YAML 동기화

Claude Code에서:
```
스펙 동기화해줘
```

또는 직접 실행:
```bash
python3 scripts/sync_specs.py "SHEET_CSV_URL" specs/ .
```

`specs/` 디렉토리에 이벤트별 YAML 파일이 생성됩니다.

---

## 사용법

Claude Code에 `/qa-checker` 스킬을 설치한 뒤 사용합니다.

### QA 검증
CSV 파일 경로를 제공하면 스펙과 대조 후 Slack 발송:
```
QA 해줘  →  CSV 경로 입력
```

### 시나리오 검증
특정 사용자 흐름(이벤트 순서 + 어트리뷰트)을 검증:
```
{시나리오명} 검증해줘
```

### 스펙 동기화
```
스펙 동기화해줘        # 시트 → YAML
yaml을 시트에 반영해줘  # YAML → 시트
```

### 어트리뷰트 QA
Braze API를 통해 유저 어트리뷰트 검증:
```
어트리뷰트 QA 해줘
```

---

## 스펙 파일 구조

```
specs/
├── _common.yaml          # 공통 프로퍼티 그룹 (이벤트 간 공유)
├── {event_name}.yaml     # 이벤트별 스펙 (시트 동기화로 자동 생성)
├── attributes/
│   └── {attr_name}.yaml  # Braze 어트리뷰트 스펙
├── scenarios/
│   └── {scenario}.yaml   # 시나리오 스펙 (이벤트 순서 + 어트리뷰트)
└── business_rules.md     # YAML로 표현 어려운 복잡한 조건 문서화
```

YAML을 직접 편집한 경우 `YAML → 시트` 동기화로 시트에 반영하세요.

---

## 테스트

```bash
pytest
```
