#!/bin/bash
set -e

REPO_PATH="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/.qa-checker"
SKILL_DIR="$HOME/.claude/skills/qa-checker"

echo "=== qa-checker 설치 ==="

# 1. Python 패키지 설치
echo ""
echo "[1/3] Python 패키지 설치 중..."
pip3 install -r "$REPO_PATH/requirements.txt" --quiet
echo "  완료"

# 2. 스킬 설치
echo ""
echo "[2/3] Claude Code 스킬 설치 중..."
mkdir -p "$SKILL_DIR"
cp "$REPO_PATH/skill.md" "$SKILL_DIR/skill.md"
echo "  완료: $SKILL_DIR/skill.md"

# 3. config 생성
echo ""
echo "[3/3] 설정 파일 확인 중..."
mkdir -p "$CONFIG_DIR"

if [ -f "$CONFIG_DIR/config.yaml" ]; then
  echo "  이미 존재: $CONFIG_DIR/config.yaml (덮어쓰지 않음)"
else
  sed "s|/path/to/qa-checker|$REPO_PATH|g" "$REPO_PATH/config.yaml.example" > "$CONFIG_DIR/config.yaml"
  echo "  생성됨: $CONFIG_DIR/config.yaml"
  echo ""
  echo "  ⚠️  아래 항목을 직접 수정해주세요:"
  echo "     - slack.bot_token"
  echo "     - slack.channel / slack.channel_id"
  echo "     - sheet.specs_url"
fi

echo ""
echo "=== 설치 완료 ==="
echo ""
echo "Claude Code에서 /qa-checker 로 실행하세요."
