# QA Checker

이벤트 로그 CSV를 YAML 스펙과 비교해 프로퍼티명·타입·필수값·허용값을 검증하고, 결과를 Slack으로 알립니다.

## 시작하기

### 1. 레포 클론

```bash
git clone https://github.com/YOUR_ORG/qa-checker.git
cd qa-checker
```

### 2. 패키지 설치

```bash
pip3 install -r requirements.txt
```

또는 `install.sh`를 실행하면 config 파일 생성도 함께 안내합니다:

```bash
bash install.sh
```

### 3. 설정 파일 생성

```bash
cp config.yaml.example ~/.qa-checker/config.yaml
```

`~/.qa-checker/config.yaml`을 열어 아래 항목을 채워주세요:

| 항목 | 설명 |
|------|------|
| `repo_path` | 이 레포를 클론한 절대 경로 |
| `slack.bot_token` | Slack Bot Token (`xoxb-...`) |
| `slack.channel` | 결과를 발송할 Slack 채널명 |
| `slack.channel_id` | 채널 ID |
| `braze.api_key` | Braze REST API Key (어트리뷰트 QA 시 필요) |
| `braze.server` | Braze 서버 (예: `rest.iad-01`) |
| `sheet.specs_url` | 구글 시트 CSV export URL (시트→YAML 동기화 시 필요) |
| `sheet.sheet_id` | 구글 시트 ID (YAML→시트 동기화 시 필요) |
| `sheet.service_account` | 서비스 계정 JSON 경로 |

### 4. 스펙 파일 작성

`specs/` 디렉토리에 이벤트별 YAML 파일을 추가하세요. `specs/example_event.yaml`을 참고하세요.

## 사용법

Claude Code에서 `/qa-checker` 스킬을 통해 실행합니다.

- **QA 검증**: CSV 파일 경로를 제공하면 스펙과 대조해 검증 후 Slack 발송
- **시나리오 검증**: `/qa-checker {시나리오명} 검증`
- **스펙 동기화**: 구글 시트 ↔ YAML 양방향 동기화
- **어트리뷰트 QA**: Braze API를 통한 유저 어트리뷰트 검증

## 스펙 파일 구조

```
specs/
├── _common.yaml          # 공통 프로퍼티 그룹
├── {event_name}.yaml     # 이벤트별 스펙
├── attributes/
│   └── {attr_name}.yaml  # 어트리뷰트 스펙
└── scenarios/
    └── {scenario}.yaml   # 시나리오 스펙
```

## 테스트

```bash
pytest
```
