# Python 3.12 베이스 이미지
FROM python:3.12-slim

# 작업 디렉토리
WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# HF 캐시 경로 (필요 시)
ENV HF_HOME=/app/.cache/huggingface

# ⭐ 모델 미리 다운로드 (이미지에 포함) ⭐
# 1) 임베딩 모델
RUN python - <<'PY'
from sentence_transformers import SentenceTransformer
print("📥 임베딩 모델 다운로드 중... (intfloat/multilingual-e5-large-instruct, ~2.5GB)")
SentenceTransformer("intfloat/multilingual-e5-large-instruct")
print("✅ 임베딩 모델 다운로드 완료!")
PY

# 2) 리랭커 모델 (dragonkue/bge-reranker-v2-m3-ko)
RUN python - <<'PY'
from sentence_transformers import CrossEncoder
print("📥 리랭커 다운로드 중... (dragonkue/bge-reranker-v2-m3-ko)")
CrossEncoder("dragonkue/bge-reranker-v2-m3-ko")
print("✅ 리랭커 다운로드 완료!")
PY

# 애플리케이션 코드 복사
COPY backend/ ./backend/
COPY api/ ./api/

# 포트 노출 (Hugging Face는 7860 사용)
EXPOSE 7860

# Python 출력 버퍼링 비활성화 (로그 즉시 출력)
ENV PYTHONUNBUFFERED=1

# FastAPI 실행 (Uvicorn)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860", "--log-level", "info"]
