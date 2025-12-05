#!/bin/bash

# 설정 파일 전환 스크립트
# 사용법: ./scripts/switch_config.sh [config_name]
# 예시: ./scripts/switch_config.sh chunking

CONFIG_NAME=${1:-"baseline"}
CONFIG_FILE="configs/${CONFIG_NAME}.env"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 설정 파일을 찾을 수 없습니다: $CONFIG_FILE"
    echo ""
    echo "사용 가능한 설정:"
    ls -1 configs/*.env | sed 's/configs\//  - /' | sed 's/\.env//'
    exit 1
fi

# .env 파일 백업
if [ -f ".env" ]; then
    cp .env .env.backup
    echo "💾 기존 .env 백업 완료 (.env.backup)"
fi

# 설정 파일 복사
cp "$CONFIG_FILE" .env
echo "✅ 설정 전환 완료: $CONFIG_NAME"
echo ""
echo "현재 설정:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
grep "^WANDB_" .env | grep -v "WANDB_ENABLED"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
