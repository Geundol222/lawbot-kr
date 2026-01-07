# 로깅 전략 분석 및 개선안

## 📊 현재 로깅 전략 (wandb_logger.py)

### ✅ 잘 되고 있는 부분

1. **세션별 Run 관리**
   - 각 대화 세션마다 별도 WandB run 생성
   - session_id 기반 추적 가능

2. **모듈별 로거 분리**
   - AgenticRAGLogger, VectorSearchLogger, LawAPILogger, FastAPILogger
   - 각 모듈의 관심사 분리

3. **실시간 모니터링 메트릭**
   - `tool/{tool_name}/execution_time`
   - `vector_search/search_latency`
   - `law_api/response_time`

### ❌ 문제점

#### 1. 모니터링 vs 평가 메트릭 혼재

**현재 로깅:**
```python
# 운영 모니터링용 메트릭
"agentic_rag/total_execution_time": 7234,
"agentic_rag/tool_calls_count": 3,
"vector_search/top_similarity": 0.85
```

**부족한 평가 메트릭:**
```python
# 실험 비교용 메트릭 (없음!)
"eval/recall_at_3": 0.0,
"eval/citation_f1": 0.0,
"eval/faithfulness": 0.0
```

→ **문제**: 성능 비교 실험 불가능

---

#### 2. Ground Truth 없음

**현재:** 검색 결과만 로깅, 정답 여부 판단 불가
```python
{
    "top_similarity": 0.85,
    "results_count": 5
}
```

**필요:** 정답 조문과 비교하여 Recall 계산
```python
{
    "retrieved_articles": ["민법 750", "민법 751"],
    "ground_truth_articles": ["민법 750"],  # 없음!
    "recall_at_3": 1.0  # 계산 불가!
}
```

→ **문제**: 검색 품질을 정량적으로 측정 불가

---

#### 3. 실험 구분 불가

**현재:** 모든 요청이 동일하게 로깅됨
- Vanilla RAG vs Self-RAG 구분 없음
- A/B 테스트 불가능

**필요:**
```python
wandb.init(
    project="lawbot-kr-evaluation",
    tags=["vanilla_rag", "v1.0"],  # 실험 구분
    config={"mode": "vanilla"}
)
```

→ **문제**: 비교 실험 시 결과 분리 불가

---

#### 4. 집계 메트릭 부재

**현재:** 개별 쿼리만 로깅
```python
wandb.log({"response_time": 7234}, step=0)
wandb.log({"response_time": 8123}, step=1)
wandb.log({"response_time": 6890}, step=2)
```

**필요:** 전체 평균/중앙값
```python
wandb.run.summary["avg_response_time"] = 7415
wandb.run.summary["median_response_time"] = 7234
wandb.run.summary["p95_response_time"] = 8100
```

→ **문제**: WandB에서 실험 간 비교 어려움

---

#### 5. 오프라인 평가 불가

**현재:** 실시간 로깅만 가능
- Streamlit 앱 실행 중에만 로깅
- 배치 평가 스크립트 없음

**필요:** 오프라인 평가 실행기
```python
evaluator = OfflineEvaluator(
    eval_dataset="datasets/eval_questions.json",
    mode="vanilla"
)
evaluator.run_evaluation()
```

→ **문제**: 100개 질문으로 체계적 평가 불가

---

## 🎯 새로운 이중 로깅 전략

### 전략 1: 운영 모니터링 (기존 유지)

**목적:** 실시간 성능 모니터링, 에러 추적

**파일:** `wandb_logger.py`

**메트릭:**
- Latency: `response_time`, `search_latency`, `api_response_time`
- Throughput: `request_count`, `concurrent_users`
- Error Rate: `error_rate`, `timeout_count`
- Resource: `total_tokens`, `api_calls`

**사용 시점:** Streamlit 앱 실행 중 (실시간)

---

### 전략 2: 평가 메트릭 (신규 추가)

**목적:** 실험 비교, A/B 테스트

**파일:** `evaluation_metrics.py`, `evaluator.py`

**메트릭:**

#### Retrieval Metrics
- `recall_at_3`: 상위 3개 결과에 정답 포함 비율
- `mrr`: Mean Reciprocal Rank
- `ndcg_at_3`: Normalized Discounted Cumulative Gain

#### Citation Metrics
- `citation_precision`: 인용한 법령 중 정답 비율
- `citation_recall`: 정답 법령 중 인용한 비율
- `citation_f1`: F1 score

#### Answer Quality (LLM 기반)
- `faithfulness`: 검색 결과 기반 답변 여부 (0-1)
- `relevance`: 질문과의 관련성 (0-1)
- `completeness`: 답변 완성도 (0-1)

#### Cost & Latency
- `response_time_ms`
- `total_tokens`
- `api_calls`

**사용 시점:** 오프라인 배치 평가

---

## 📁 새로운 파일 구조

```
backend/src/monitoring/
├── __init__.py                  # 업데이트
├── wandb_logger.py              # 기존 (운영 모니터링)
├── evaluation_metrics.py        # 신규 (평가 메트릭 계산)
├── evaluator.py                 # 신규 (오프라인 평가 실행기)
└── LOGGING_STRATEGY.md          # 이 문서

datasets/
├── eval_questions.json          # 평가용 질문 세트 (10개 → 100개로 확장)
├── ground_truth.json            # 정답 데이터 (수동 레이블링)
└── README.md
```

---

## 🚀 사용 방법

### 1. 운영 모니터링 (실시간)

```python
# app.py 또는 agent_streaming.py에서 사용
from src.monitoring import get_wandb_logger, AgenticRAGLogger

wandb_logger = get_wandb_logger(session_id=session_id)
rag_logger = AgenticRAGLogger(wandb_logger)

rag_logger.start_session(question)
rag_logger.log_tool_call("vector_search", args, result, execution_time)
rag_logger.end_session(answer, total_tokens)
```

### 2. 평가 메트릭 (오프라인)

```python
# 단일 모드 평가
from src.monitoring import OfflineEvaluator

evaluator = OfflineEvaluator(
    eval_dataset_path="datasets/eval_questions.json",
    ground_truth_path="datasets/ground_truth.json",
    mode="current",
    wandb_experiment="baseline_v1"
)

evaluator.run_evaluation()
```

### 3. 비교 실험

```python
# Vanilla vs Current vs Full Self-RAG
from src.monitoring import run_comparison_experiment

run_comparison_experiment(
    eval_dataset_path="datasets/eval_questions.json",
    ground_truth_path="datasets/ground_truth.json",
    modes=["vanilla", "current", "full_self_rag"]
)
```

---

## 📊 WandB 프로젝트 구조

### 프로젝트 1: lawbot-kr (운영 모니터링)

**목적:** 실시간 성능 추적

**Run 단위:** 1 세션 = 1 Run

**그룹화:**
- Group: `daily_20251229`
- Tags: `v2.0`, `production`

**주요 메트릭:**
- `fastapi/avg_response_time`
- `fastapi/concurrent_users`
- `vector_search/search_latency`

---

### 프로젝트 2: lawbot-kr-evaluation (평가)

**목적:** 실험 비교

**Run 단위:** 1 실험 모드 = 1 Run

**그룹화:**
- Group: `eval_20251229`
- Tags: `vanilla_rag`, `current`, `full_self_rag`, `comparison_v1`

**주요 메트릭:**
- `eval_summary/vanilla/avg_recall_at_3`
- `eval_summary/current/avg_citation_f1`
- `eval_summary/full_self_rag/avg_faithfulness`

**Summary (최종 메트릭):**
```python
wandb.run.summary["avg_recall_at_3"] = 0.85
wandb.run.summary["avg_response_time_ms"] = 7234
wandb.run.summary["total_questions"] = 100
```

---

## 🔄 마이그레이션 계획

### 1단계: 평가 시스템 구축 (오늘)

- [x] `evaluation_metrics.py` 작성
- [x] `evaluator.py` 작성
- [x] `datasets/eval_questions.json` 생성 (10개)
- [x] `datasets/ground_truth.json` 생성 (10개)
- [x] `monitoring/__init__.py` 업데이트

### 2단계: AgenticRAG 평가 모드 추가 (내일)

```python
class AgenticRAG:
    def __init__(self, mode="current"):
        """
        mode:
            - "vanilla": Query Expansion만
            - "current": 예외조항 체크 포함
            - "full_self_rag": 답변 품질 평가 포함
        """
        self.mode = mode

    def run_with_metrics(self, question: str) -> tuple:
        """
        평가용 실행 (retrieved_docs, metrics 반환)

        Returns:
            (answer, retrieved_docs, metrics)
        """
        # TODO: 구현 필요
```

### 3단계: 첫 실험 실행 (1/3-1/5)

```bash
# 1. 10개 질문으로 테스트
python -m src.monitoring.evaluator

# 2. Ground Truth 검증 및 수정
# 3. 100개로 확장
```

### 4단계: 비교 실험 (1/6-1/10)

```bash
# Vanilla vs Current vs Full Self-RAG
python -m src.monitoring.evaluator --comparison
```

---

## 💡 핵심 포인트

1. **기존 로깅은 유지** - 운영 모니터링용
2. **새로운 평가 시스템 추가** - 실험 비교용
3. **두 시스템은 독립적** - 서로 간섭하지 않음
4. **Ground Truth가 핵심** - 정량적 평가의 시작점
5. **오프라인 평가로 체계적 비교** - 배치 실행으로 공정한 비교
