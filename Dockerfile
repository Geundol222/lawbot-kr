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

# ⭐ 임베딩 모델 미리 다운로드 (이미지에 포함) ⭐
# Docker 이미지 빌드 시 한 번만 다운로드되고, 컨테이너 실행 시에는 다운로드 안 함!
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
print('📥 임베딩 모델 다운로드 중... (2.5GB)'); \
model = SentenceTransformer('intfloat/multilingual-e5-large-instruct'); \
print('✅ 모델이 이미지에 포함되었습니다!')"

# 애플리케이션 코드 복사
COPY backend/ ./backend/
COPY api/ ./api/

# 포트 노출 (Hugging Face는 7860 사용)
EXPOSE 7860

# FastAPI 실행 (Uvicorn)
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
