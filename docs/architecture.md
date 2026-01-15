# 시스템 아키텍처

## 1. 전체 시스템 아키텍처

```mermaid
flowchart TB
    subgraph Client["클라이언트"]
        UI[Next.js UI<br/>React 19, TypeScript]
    end

    subgraph Backend["백엔드 서버"]
        API[FastAPI Server<br/>Python 3.12]
        Agent[Agentic RAG<br/>LangGraph]

        subgraph Tools["Agent Tools"]
            VectorDB[Vector Search<br/>Semantic + BM25]
            LawAPI[Law API Search<br/>law.go.kr]
            ExceptionCheck[Exception Checker<br/>Self-RAG]
        end
    end

    subgraph Storage["데이터 저장소"]
        Supabase[(Supabase PostgreSQL)]
        VectorStore[(pgvector<br/>8,182 법령 조문)]
        BM25Cache[(BM25 Index<br/>Pickle Cache)]
        ChatHistory[(대화 이력<br/>conversations)]
    end

    subgraph External["외부 API"]
        LawGov[법제처 Open API<br/>law.go.kr]
        GeminiAPI[Google Gemini API<br/>2.5 Flash]
    end

    subgraph Monitoring["모니터링"]
        WandB[WandB<br/>실험 추적]
        Eval[Offline Evaluator<br/>Ground Truth]
    end

    UI -->|HTTP/SSE| API
    API -->|실시간 스트리밍| Agent

    Agent -->|1. 벡터 검색| VectorDB
    Agent -->|2. 외부 API 검색| LawAPI
    Agent -->|3. 예외 조항 체크| ExceptionCheck

    VectorDB -->|조문 조회| VectorStore
    VectorDB -->|키워드 검색| BM25Cache
    LawAPI -->|법령 검색| LawGov
    ExceptionCheck -->|LLM 판단| GeminiAPI

    Agent -->|답변 생성| GeminiAPI
    API -->|대화 저장| ChatHistory

    Agent -.->|메트릭 로깅| WandB
    Eval -.->|평가 결과| WandB

    VectorStore -.->|임베딩 모델| EmbedModel[multilingual-e5-large]
    VectorStore -.->|Reranker| Reranker[bge-reranker-v2-m3-ko]

    style UI fill:#e1f5ff
    style Agent fill:#fff4e1
    style VectorStore fill:#ffe1f5
    style GeminiAPI fill:#e1ffe1
```

## 2. Agentic RAG 실행 플로우

```mermaid
flowchart TD
    Start([사용자 질문]) --> Init[StateGraph 초기화]

    Init --> AgentNode[Agent Node<br/>LLM + Tool Selection]

    AgentNode --> Decision{Tool 호출?}

    Decision -->|Yes| ToolNode[Tool Execution Node]
    Decision -->|No| Answer[Answer Node<br/>답변 생성]

    ToolNode --> ToolType{Tool 타입}

    ToolType -->|search_vector_db| Vector[Vector Search]
    ToolType -->|search_law_by_api| API[Law API Search]
    ToolType -->|check_exceptions_needed| Exception[Exception Check]

    Vector --> VectorProcess[벡터 검색 프로세스]

    subgraph VectorProcess["벡터 검색 상세 프로세스"]
        V1[Query Expansion<br/>서브쿼리 2~4개 생성]
        V2[Parallel Search<br/>Semantic + BM25]
        V3[Merge & Deduplicate<br/>최대 후보 병합]
        V4[Rerank<br/>Cross-Encoder]
        V5[Top-K 반환<br/>기본 5개]

        V1 --> V2 --> V3 --> V4 --> V5
    end

    API --> APIProcess[법제처 API 호출<br/>법령명/조문 검색]

    Exception --> ExceptionProcess[Self-RAG 예외 체크]

    subgraph ExceptionProcess["예외 조항 체크 프로세스"]
        E1{검색된 법령에<br/>'단서' 포함?}
        E2[LLM에게 예외 판단 요청]
        E3[예외 적용 여부 반환]

        E1 -->|Yes| E2 --> E3
        E1 -->|No| E3
    end

    VectorProcess --> ToolResult[Tool 결과 State에 저장]
    APIProcess --> ToolResult
    ExceptionProcess --> ToolResult

    ToolResult --> AgentNode

    Answer --> StreamStart[SSE 스트리밍 시작]

    StreamStart --> LLMStream[Gemini 2.5 Flash<br/>실시간 답변 생성]

    LLMStream --> ValidateResponse{응답 검증}

    ValidateResponse -->|인용 누락| AddCitation[조문 번호 추가]
    ValidateResponse -->|정상| SaveChat[대화 이력 저장]

    AddCitation --> SaveChat

    SaveChat --> End([사용자에게 반환])

    style AgentNode fill:#fff4e1
    style ToolNode fill:#e1f5ff
    style Answer fill:#e1ffe1
    style VectorProcess fill:#ffe1f5
    style ExceptionProcess fill:#fff0e1
```

## 3. 데이터 파이프라인 아키텍처

```mermaid
flowchart LR
    subgraph Collection["1. 데이터 수집"]
        LawAPI[법제처 Open API]
        Crawler[법령 크롤러<br/>fetch_all_laws.py]

        LawAPI -->|법령 목록 조회| Crawler
        Crawler -->|조문별 크롤링| RawData[Raw 법령 데이터<br/>JSON]
    end

    subgraph Processing["2. 데이터 처리"]
        RawData --> Parser[파싱 & 정제]

        Parser --> Clean[조문 텍스트 정제]
        Clean --> Chunk[청킹 전략<br/>조 단위 분할]

        Chunk --> MetaData[메타데이터 추가<br/>법령명, 조문번호, MST]
    end

    subgraph Embedding["3. 임베딩 생성"]
        MetaData --> EmbedModel[Embedding Model<br/>e5-large-instruct]

        EmbedModel --> VectorEmbed[1024차원 벡터 생성]

        MetaData --> BM25Build[BM25 인덱스 구축<br/>Mecab 형태소 분석]
    end

    subgraph Storage["4. 저장"]
        VectorEmbed --> PGVector[(Supabase pgvector<br/>law_cache 테이블)]
        BM25Build --> BM25File[(BM25 Index<br/>bm25_index.pkl)]

        PGVector --> IndexCreate[벡터 인덱스 생성<br/>HNSW]
    end

    subgraph Retrieval["5. 검색 (런타임)"]
        UserQuery[사용자 질문]

        UserQuery --> QueryEmbed[Query 임베딩]
        UserQuery --> QueryTokenize[형태소 분석]

        QueryEmbed --> SemanticSearch[Semantic Search<br/>코사인 유사도]
        QueryTokenize --> BM25Search[BM25 Search<br/>Okapi BM25]

        SemanticSearch --> PGVector
        BM25Search --> BM25File

        PGVector --> SemanticResults[Semantic Top-15]
        BM25File --> BM25Results[BM25 Top-15]

        SemanticResults --> Merge[Hybrid Merge]
        BM25Results --> Merge

        Merge --> Rerank[Reranker<br/>bge-reranker]

        Rerank --> FinalResults[최종 Top-5 결과]
    end

    subgraph Monitoring["6. 평가 & 모니터링"]
        FinalResults -.-> Metrics[검색 메트릭<br/>Recall, MRR, NDCG]
        FinalResults -.-> Quality[답변 품질<br/>Citation F1, Faithfulness]

        Metrics --> WandB[WandB 대시보드]
        Quality --> WandB

        GroundTruth[Ground Truth<br/>15개 질문] -.-> OfflineEval[Offline Evaluator]

        OfflineEval --> WandB
    end

    style Collection fill:#e1f5ff
    style Processing fill:#fff4e1
    style Embedding fill:#ffe1f5
    style Storage fill:#e1ffe1
    style Retrieval fill:#fff0e1
    style Monitoring fill:#f0e1ff
```

## 4. 핵심 컴포넌트 상세

### 4.1 Vector Search (Hybrid Retrieval)

**특징**:
- **Semantic Search**: multilingual-e5-large-instruct (1024-dim)
- **BM25 Search**: Okapi BM25 with Mecab tokenizer
- **Reranker**: BGE Reranker v2-m3 Korean
- **Fusion**: Semantic + BM25 병합 후 Rerank

**성능**:
- 검색 대상: 8,182개 조문
- 평균 검색 시간: 200~300ms
- Recall@5: 45% (현재) → 90% (목표)

### 4.2 Agentic RAG (LangGraph)

**구조**:
- **State**: AgentState (typed dict with messages, context, retrieved_docs)
- **Nodes**: Agent Node, Tool Node, Answer Node
- **Tools**: 3개 (vector_search, law_api_search, check_exceptions)
- **LLM**: Gemini 2.5 Flash

**실행 흐름**:
1. Agent가 Tool 선택 (LLM 판단)
2. Tool 병렬 실행 (ThreadPoolExecutor)
3. 결과를 State에 누적
4. Agent가 추가 Tool 필요 여부 판단
5. 충분한 정보 수집 시 답변 생성

### 4.3 Self-RAG (예외 조항 체크)

**목적**:
- 법령의 "단서" 조항 (예: "다만, ...", "단, ...") 자동 감지
- 사용자 상황이 예외에 해당하는지 LLM 판단

**예시**:
```
질문: "5인 미만 사업장에서 해고 예고수당 받을 수 있어?"

근로기준법 제11조: "이 법은 상시 5명 이상의 근로자를 사용하는 모든 사업 또는 사업장에 적용한다. 다만, ..."

→ check_exceptions_needed() 호출
→ LLM 판단: "5인 미만은 예외에 해당, 제11조 적용 제외"
→ 정확한 답변 생성
```

### 4.4 데이터베이스 스키마

**law_cache 테이블** (Supabase):
```sql
CREATE TABLE law_cache (
    id BIGSERIAL PRIMARY KEY,
    law_name TEXT NOT NULL,           -- 법령명
    article TEXT,                      -- 조문 번호 (예: "제750조")
    mst TEXT,                          -- 법령 고유 ID
    title TEXT,                        -- 조문 제목
    content TEXT,                      -- 조문 내용
    embedding VECTOR(1024),            -- 임베딩 벡터
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_law_cache_embedding ON law_cache
USING hnsw (embedding vector_cosine_ops);

CREATE INDEX idx_law_name_article ON law_cache(law_name, article);
```

**conversations 테이블**:
```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    messages JSONB NOT NULL,           -- 대화 메시지 배열
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 5. 성능 최적화

### 5.1 검색 최적화
- **HNSW 인덱스**: 벡터 검색 O(log N) 시간 복잡도
- **BM25 캐시**: Pickle 직렬화로 빠른 로딩 (1초 이내)
- **병렬 검색**: Semantic + BM25 동시 실행 (ThreadPoolExecutor)
- **Reranking**: 상위 후보만 Cross-Encoder 적용 (비용 절감)

### 5.2 LLM 최적화
- **스트리밍**: SSE로 실시간 답변 전송 (UX 개선)
- **모델 선택**:
  - 답변 생성: Gemini 2.5 Flash - 빠르고 정확
  - Query Expansion: Gemini 2.5 Flash Lite - 초경량
- **프롬프트 캐싱**: 반복적인 시스템 프롬프트 캐싱 (비용 절감)

### 5.3 인프라 최적화
- **Supabase Edge Functions**: 서버리스 배포
- **pgvector**: PostgreSQL 네이티브 벡터 검색 (별도 벡터 DB 불필요)
- **BM25 메모리 캐싱**: 8,182 문서 인덱스를 메모리 상주

## 6. 모니터링 & 평가

### 6.1 실시간 모니터링 (WandB)
- **검색 메트릭**: 검색 시간, 결과 수, Top 유사도
- **LLM 메트릭**: 토큰 사용량, API 호출 횟수, 응답 시간
- **Agent 메트릭**: Tool 호출 횟수, 검색 반복 횟수

### 6.2 오프라인 평가 (Ground Truth)
- **데이터셋**: 15개 테스트 질문 (상황별, 난이도별)
- **평가 지표**:
  - Retrieval: Recall@3/5/10, MRR, NDCG@3
  - Generation: Citation F1, Faithfulness, Relevance
  - Cost: 응답 시간, 토큰 수
- **자동 평가**: CI/CD 파이프라인 통합 가능

### 6.3 현재 성능 (2026-01-04 평가)
| Metric | 값 | 목표 |
|--------|-----|------|
| Recall@3 | 35% | 80% |
| Recall@5 | 45% | 90% |
| Recall@10 | 50% | 95% |
| Citation F1 | 30% | 80% |
| 평균 응답 시간 | 113초 | 60초 |

## 7. 기술 스택

### Backend
- **Language**: Python 3.12
- **Framework**: FastAPI 0.104+
- **Agent**: LangGraph 1.0.4
- **LLM**: Google Gemini API (2.5 Flash)
- **Embedding**: multilingual-e5-large-instruct
- **Reranker**: bge-reranker-v2-m3-ko
- **BM25**: rank-bm25 + Kiwi (한국어 형태소 분석기)

### Frontend
- **Framework**: Next.js 16.0
- **Language**: TypeScript
- **UI**: React 19, Tailwind CSS
- **State**: React Query, Context API

### Infrastructure
- **Database**: Supabase (PostgreSQL + pgvector)
- **Deployment**: HuggingFace Spaces (Backend), Vercel (Frontend)
- **Monitoring**: WandB
- **Version Control**: Git + GitHub

### External APIs
- **Law Data**: 법제처 Open API (law.go.kr)
- **LLM**: Google Gemini API
- **Embedding**: Hugging Face models (self-hosted)

## 8. 배포 아키텍처

```mermaid
flowchart TB
    subgraph Production["프로덕션 환경"]
        User[사용자]

        User -->|HTTPS| Vercel[Vercel<br/>Next.js Frontend]
        Vercel -->|API 호출| Railway[Railway/Render<br/>FastAPI Backend]

        Railway -->|Vector 검색| Supabase[(Supabase<br/>PostgreSQL + pgvector)]
        Railway -->|LLM 호출| Gemini[Google Gemini API]
        Railway -->|법령 조회| LawGov[법제처 Open API]

        Railway -.->|메트릭| WandB[WandB 대시보드]
    end

    subgraph Development["개발 환경"]
        DevFE[Local Frontend<br/>npm run dev]
        DevBE[Local Backend<br/>uvicorn]

        DevBE -->|테스트| LocalDB[(Local PostgreSQL)]
        DevBE -.->|평가| Evaluator[Offline Evaluator]
    end

    GitHub[GitHub Repository] -->|Deploy| Vercel
    GitHub -->|Deploy| Railway

    Evaluator -.->|평가 결과| WandB

    style Vercel fill:#e1f5ff
    style Railway fill:#fff4e1
    style Supabase fill:#ffe1f5
    style Gemini fill:#e1ffe1
```

## 9. 보안 & 권한

### API 키 관리
- **환경 변수**: `.env` 파일 (Git 제외)
- **Supabase**: Row Level Security (RLS) 적용
- **CORS**: 허용된 도메인만 API 접근

### 데이터 보호
- **대화 이력**: UUID 기반 익명화
- **개인정보**: 수집하지 않음 (법률 상담 내용만 저장)
- **HTTPS**: 모든 통신 암호화

## 10. 확장성

### 수평 확장
- **Backend**: 무상태(stateless) 서버로 설계 → 여러 인스턴스 배포 가능
- **Database**: Supabase 자동 스케일링
- **LLM API**: Rate limit 내에서 병렬 호출

### 수직 확장
- **벡터 인덱스**: 100만 개 조문까지 확장 가능 (현재 8천 개)
- **BM25**: 메모리 허용 범위 내 무제한
- **캐싱**: Redis 도입으로 검색 결과 캐싱 가능

---

**작성일**: 2026-01-04
**버전**: 1.0
**작성자**: Claude Sonnet 4.5
