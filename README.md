---
title: 한국 법령 챗봇 (Lawbot-KR)
emoji: ⚖️
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# 한국 법령 챗봇 (Lawbot-KR)

벡터 검색과 Agentic RAG를 결합한 한국 법령 상담 AI 챗봇

## ✨ 주요 기능

- 🤖 **Agentic RAG**: LangGraph 기반 자율 도구 선택 및 실행
- 🔍 **하이브리드 검색**: 벡터 검색 + API 검색 자동 전환
- 📊 **WandB 로깅**: 실험 추적 및 성능 비교
- 🧩 **청킹 지원**: 긴 조문을 청크로 분할하여 임베딩 (500자 청크, 100자 오버랩)
- ⚡ **최적화**: 불필요한 API 호출 제거, 벡터 검색 결과에 조문 내용 포함

---

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 저장소 클론
git clone https://github.com/your-username/lawbot-kr.git
cd lawbot-kr

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일을 열어 API 키 입력
```

`.env` 파일 예시:
```bash
GOOGLE_API_KEY=your_google_api_key_here
SUPABASE_URL=your_supabase_url_here
SUPABASE_ANON_KEY=your_supabase_anon_key_here
LAW_API_OC=your_law_api_key_here
WANDB_ENABLED=false  # WandB 사용 시 true
```

### 2. Supabase 벡터 검색 설정

Supabase에서 벡터 검색 RPC 함수를 생성해야 합니다:

1. [Supabase 대시보드](https://supabase.com) 접속
2. SQL Editor 열기
3. 다음 SQL 실행:

```sql
-- pgvector 확장 활성화
create extension if not exists vector;

-- 기존 함수 삭제
DROP FUNCTION IF EXISTS match_law_documents(vector, float, int);
DROP FUNCTION IF EXISTS match_law_documents(vector, double precision, integer);

-- RPC 함수 생성
CREATE OR REPLACE FUNCTION match_law_documents(
  query_embedding vector(1024),
  match_threshold float DEFAULT 0.0,
  match_count int DEFAULT 10
)
RETURNS TABLE (
  id bigint,
  law_name text,
  article text,
  mst text,
  content text,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    law_cache.id,
    law_cache.law_name::text,
    law_cache.article::text,
    law_cache.mst::text,
    law_cache.content::text,
    (1 - (law_cache.embedding <=> query_embedding))::float AS similarity
  FROM law_cache
  WHERE 1 - (law_cache.embedding <=> query_embedding) >= match_threshold
  ORDER BY law_cache.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

-- RLS 비활성화
ALTER TABLE law_cache DISABLE ROW LEVEL SECURITY;
```

### 3. 임베딩 생성 (선택사항)

벡터 검색을 사용하려면 법령 임베딩을 생성해야 합니다:

```bash
# Google Colab에서 실행
# notebooks/lawbot_embedding_generation_v2.ipynb 열기
```

**특징:**
- 500자 청크, 100자 오버랩
- GPU 자동 감지
- 자동 캐시 초기화 옵션

### 4. 앱 실행

```bash
# Streamlit 웹 앱
streamlit run app.py

# FastAPI (선택사항)
cd api
uvicorn main:app --reload
```

브라우저에서 http://localhost:8501 열기

---

## 📁 프로젝트 구조

```
lawbot-kr/
├── app.py                          # Streamlit 웹 앱
├── api/
│   └── main.py                     # FastAPI 엔드포인트
├── backend/
│   └── src/
│       ├── agentic_rag.py          # Agentic RAG 메인 (도구 정의, 그래프 구성)
│       ├── agent_state.py          # Agent 상태 정의
│       ├── agent_nodes.py          # Agent 노드 로직
│       ├── agent_streaming.py      # 스트리밍 로직
│       ├── embeddings/
│       │   ├── vector_search.py    # 벡터 검색 (Supabase)
│       │   └── generate_embeddings.py  # 임베딩 생성 스크립트
│       ├── monitoring/
│       │   ├── __init__.py
│       │   └── wandb_logger.py     # WandB 로깅 시스템
│       ├── law_api.py              # 법령 API 클라이언트
│       ├── law_api_monitored.py    # 법령 API (WandB 로깅)
│       └── config.py               # 설정
├── notebooks/
│   └── lawbot_embedding_generation_v2.ipynb  # 임베딩 생성 노트북
├── configs/
│   ├── baseline.env                # v1.0 베이스라인 설정
│   ├── chunking.env                # v2.0 청킹 적용 설정
│   └── optimized.env               # v2.1 최적화 설정
└── scripts/
    ├── run_experiment.sh           # 실험 실행 스크립트
    └── switch_config.sh            # 설정 전환 스크립트
```

---

## 🔍 작동 방식

### Agentic RAG 흐름

```
1. search_vector_db(질문)
   ↓
   [유사도 ≥ 0.7]
   → 벡터 검색 성공
   → 조문 내용 포함 반환
   → 즉시 답변 생성 ✅

   [유사도 < 0.7]
   → VECTOR_DB_NO_MATCH
   → search_law_by_api(법령명)
   → API에서 조문 조회
   → 답변 생성 ✅
```

**최적화:**
- 벡터 검색 결과에 조문 내용(`content`) 포함
- `get_full_article_content` 호출 불필요 → API 호출 3회 절약
- 응답 속도 향상, 비용 절감

### 청크 기반 임베딩

긴 조문을 500자 청크로 분할하여 임베딩:

```
예: 민법 제750조 (전체 1200자)
→ 제750조_part1 (0-500자)
→ 제750조_part2 (400-900자, 100자 오버랩)
→ 제750조_part3 (800-1200자, 100자 오버랩)
```

**중복 제거:**
- 벡터 검색 시 같은 조문의 여러 청크 반환 가능
- `_deduplicate_chunks()` 메서드로 최고 유사도 청크만 유지
- `제750조_part1, _part2` → `제750조` (정규화)

---

## 🛠️ 핵심 기술 스택

| 분류 | 기술 |
|------|------|
| **LLM** | Google Gemini 2.5 Flash |
| **임베딩** | intfloat/multilingual-e5-large-instruct (1024차원) |
| **벡터 DB** | Supabase (pgvector, 코사인 유사도) |
| **Agent** | LangGraph (StateGraph, Function Calling) |
| **API** | 국가법령정보센터 Open API |
| **모니터링** | WandB (메트릭, 테이블 로깅) |
| **백엔드** | FastAPI |
| **프론트엔드** | Streamlit |

---

## 📊 WandB 실험 추적

### 실험 실행

```bash
# 베이스라인 (v1.0)
./scripts/run_experiment.sh 1.0 baseline streamlit

# 청킹 적용 (v2.0)
./scripts/run_experiment.sh 2.0 chunking streamlit

# 최적화 버전 (v2.1)
./scripts/run_experiment.sh 2.1 optimized streamlit
```

### 로깅 메트릭

**AgenticRAG:**
- `agentic_rag/total_execution_time`: 전체 실행 시간
- `agentic_rag/tool_calls_count`: 도구 호출 횟수
- `agentic_rag/total_tokens`: 토큰 사용량

**VectorSearch:**
- `vector_search/search_latency`: 검색 시간
- `vector_search/top_similarity`: 최고 유사도
- `vector_search/deduplication_count`: 중복 제거 수

**FastAPI:**
- `fastapi/request_count`: 요청 수
- `fastapi/avg_response_time`: 평균 응답 시간
- `fastapi/error_rate`: 에러율

**테이블 로깅:**
- `tool_calls_log`: 도구 호출 내역
- `vector_search_log`: 벡터 검색 로그
- `law_api_calls_log`: API 호출 로그
- `fastapi_requests_log`: HTTP 요청 로그

---

## 💬 사용 예시

### 구체적인 조문 질문
```
✅ 근로기준법 제56조가 뭐야?
✅ 민법 제750조 알려줘
✅ 헌법 제1조 내용
```

### 상황 설명 질문
```
✅ 야근수당은 얼마나 받을 수 있어?
✅ 택배가 분실되었을 때 소비자가 보호받을 수 있는 법이 있어?
✅ 월세 계약 해지하고 싶어
```

**응답 예시:**
```
📋 요약
연장근로(야근)에 대해서는 통상임금의 50% 이상을 가산하여 지급해야 합니다.

⚖️ 근거 법령
근로기준법 제56조 (연장·야간 및 휴일 근로)

📜 조문 내용
사용자는 연장근로(제53조·제59조 및 제69조 단서에 따라 연장된 시간의
근로)와 야간근로(오후 10시부터 오전 6시까지 사이의 근로) 또는 휴일근로에
대하여는 통상임금의 100분의 50 이상을 가산하여 근로자에게 지급하여야 한다.
```

---

## 🔧 문제 해결

### Supabase RPC 함수 오류

**증상:**
```
⚠️ RPC 호출 실패, 폴백 방식 사용: Could not find the function match_law_documents
```

**해결:**
위의 "Supabase 벡터 검색 설정" 섹션의 SQL을 실행하세요.

### 벡터 검색 느림

**증상:** 검색이 5초 이상 소요

**원인:** RPC 함수가 설정되지 않아 Fallback 모드로 동작 (전체 테이블 스캔)

**해결:** Supabase RPC 함수 생성 (위 참고)

### WandB 로깅 비활성화

```bash
# 환경변수 설정
export WANDB_ENABLED=false
streamlit run app.py

# 또는 .env 파일에서
WANDB_ENABLED=false
```

---

## 🎯 주요 개선 사항

### v3.0 (모듈화 및 스트리밍 완성) - 2025.12.11
- ✅ **코드 모듈화**: `agentic_rag.py` 509줄 → 238줄 (53% 감소)
  - 분리: `agent_state.py`, `agent_nodes.py`, `agent_streaming.py`
  - 객체지향 설계 원칙 적용, 유지보수성 대폭 향상
- ✅ **LLM 설정 간소화**: 중복 인스턴스 제거, 메모리 효율화
- ✅ **자연스러운 스트리밍**: 1자씩 30ms 간격 타이핑 효과
- ✅ **성능 최적화**: gemini-2.5-pro → flash (그래프 실행 12초 → 3-6초 예상)

### v2.1 (최적화 버전)
- ✅ 벡터 검색 결과에 조문 내용 포함 → API 호출 3회 절약
- ✅ Agent 프롬프트 개선 → 불필요한 도구 호출 제거
- ✅ 도구 호출 제한 증가 (3 → 10회) → 복잡한 질문 처리 개선

### v2.0 (청킹 적용)
- ✅ 500자 청크, 100자 오버랩으로 긴 조문 처리
- ✅ 청크 중복 제거 로직 (`_deduplicate_chunks`)
- ✅ Colab 환경 지원 (GPU 자동 감지)

### v1.0 (베이스라인)
- ✅ LangGraph Agentic RAG 구현
- ✅ 벡터 검색 + API 검색 하이브리드
- ✅ WandB 로깅 시스템 통합
- ✅ 커스텀 `execute_tools` (메시지 손실 해결)

---

## ⚠️ 주의사항

- 본 챗봇은 **법률 정보 제공 목적**이며, 정식 법률 자문이 아닙니다.
- 중요한 법률 문제는 반드시 **전문 변호사**와 상담하세요.
- API 키는 `.env` 파일에 저장하고 Git에 커밋하지 마세요.

---

## 📊 데이터 출처

- **법령 데이터**: [국가법령정보센터](https://www.law.go.kr/)
- **벡터 DB**: 주요 법령 조문 임베딩 (청크 기반)

---

## 🤝 기여

버그 리포트, 기능 제안, Pull Request 환영합니다!

---

## 📝 라이선스

MIT License
