#!/bin/bash

# WandB 실험 실행 스크립트
# 사용법: ./scripts/run_experiment.sh [version] [experiment_name] [app_type]
# 예시: ./scripts/run_experiment.sh 2.0 chunking streamlit

VERSION=${1:-"dev"}
EXPERIMENT=${2:-"baseline"}
APP_TYPE=${3:-"streamlit"}  # streamlit, fastapi, cli

echo "🚀 실험 시작"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 버전: v$VERSION"
echo "🔬 실험: $EXPERIMENT"
echo "💻 앱: $APP_TYPE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 환경변수 설정
export WANDB_ENABLED=true
export LAWBOT_VERSION=$VERSION
export WANDB_EXPERIMENT=$EXPERIMENT
export WANDB_GROUP=$EXPERIMENT

# 앱 실행
case $APP_TYPE in
  streamlit)
    echo "▶️  Streamlit 앱 실행 중..."
    streamlit run app.py
    ;;
  fastapi)
    echo "▶️  FastAPI 서버 실행 중..."
    python -m uvicorn api.main:app --reload
    ;;
  cli)
    echo "▶️  CLI 테스트 모드..."
    echo "질문을 입력하세요:"
    read question
    python backend/src/main.py "$question"
    ;;
  *)
    echo "❌ 알 수 없는 앱 타입: $APP_TYPE"
    echo "사용 가능: streamlit, fastapi, cli"
    exit 1
    ;;
esac
