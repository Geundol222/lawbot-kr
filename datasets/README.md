# 평가 데이터셋

## 📁 파일 구조

```
datasets/
├── eval_questions.json    # 평가용 질문 세트
├── ground_truth.json      # 정답 데이터 (수동 레이블링)
└── README.md
```

## 📋 eval_questions.json

평가에 사용할 질문 목록

**구조:**
```json
[
  {
    "id": "q001",
    "question": "민법 제750조가 뭐야?",
    "category": "specific_article | situation",
    "difficulty": "easy | medium | hard"
  }
]
```

**카테고리:**
- `specific_article`: 특정 조문 질문 (예: "민법 제750조는?")
- `situation`: 상황 설명 질문 (예: "야근수당은 얼마나 받아?")

**난이도:**
- `easy`: 단일 조문 답변 (1개 법령)
- `medium`: 2-3개 조문 필요
- `hard`: 여러 법령, 예외조항, 복잡한 추론 필요

---

## 🎯 ground_truth.json

각 질문의 정답 데이터 (평가 메트릭 계산용)

**구조:**
```json
{
  "q001": {
    "articles": ["민법 750", "민법 751"],
    "context": "정답 설명 (선택)",
    "expected_keywords": ["손해배상", "불법행위"]
  }
}
```

**필드:**
- `articles` (필수): 정답 법령 조문 리스트 (형식: "법령명 조문번호")
  - 예: `["민법 750", "근로기준법 56"]`
  - Retrieval Metrics (Recall@k, MRR) 계산에 사용

- `article_content` (자동 수집): 실제 법령 조문 내용
  - 예: `{"민법 750": "고의 또는 과실로 인한..."}`
  - 법령 API로 자동 수집 (`collect_article_content.py`)
  - Faithfulness 평가 시 "정확한 법령 내용" 기준으로 사용

- `reference_answer` (선택): 모범 답변 예시
  - 사람이 직접 작성한 고품질 답변
  - Answer Quality 평가 시 참고용 (BLEU, ROUGE 등)

- `expected_keywords` (선택): 예상 키워드 (간단 체크용)
  - 답변에 포함되어야 할 핵심 단어

- `retrieved_docs` (자동 수집): 고정된 검색 결과
  - `collect_retrieval_results.py`로 자동 수집
  - 재현성 확보용

---

## ✍️ Ground Truth 레이블링 가이드

### 1. 질문 추가 (수동)

`eval_questions.json`에 질문 추가:
```json
{
  "id": "q011",
  "question": "민법 제750조가 뭐야?",
  "category": "specific_article",
  "difficulty": "easy"
}
```

### 2. 정답 조문 레이블링 (수동)

`ground_truth.json`에 **정답 조문**만 추가:
```json
{
  "q011": {
    "articles": ["민법 750"],
    "expected_keywords": ["불법행위", "손해배상"]
  }
}
```

**주의:**
- `articles`: Retrieval 평가 기준 (Recall@k, MRR 계산)
- `expected_keywords`: 선택 사항 (간단 체크용)
- ⚠️ **`context`, `reference_answer` 등 임의로 작성하지 마세요!**

### 3. 실제 조문 내용 수집 (자동)

```bash
python scripts/collect_article_content.py
```

→ `article_content` 필드가 자동으로 추가됨:
```json
{
  "q011": {
    "articles": ["민법 750"],
    "expected_keywords": ["불법행위", "손해배상"],
    "article_content": {
      "민법 750": "고의 또는 과실로 인한 위법행위로..."  // 법령 API로 자동 수집
    }
  }
}
```

### 4. 검색 결과 수집 (자동)

```bash
python scripts/collect_retrieval_results.py
```

→ `retrieved_docs` 필드가 자동으로 추가됨 (재현성 확보)

---

## 🤖 자동 수집 스크립트

### `collect_article_content.py`
- **목적**: 실제 법령 조문 내용 수집
- **입력**: `articles` 필드
- **출력**: `article_content` 필드
- **사용**: Faithfulness 평가 시 "정확한 법령 내용" 기준

### `collect_retrieval_results.py`
- **목적**: 고정된 검색 결과 수집
- **입력**: `eval_questions.json`
- **출력**: `retrieved_docs` 필드
- **사용**: 재현성 확보 (매번 같은 검색 결과)

---

## 🧪 평가 실행 방법

### 1. 단일 모드 평가

```bash
cd backend
python -m src.monitoring.evaluator
```

### 2. 비교 실험 (Vanilla vs Current vs Full Self-RAG)

```python
from src.monitoring import run_comparison_experiment

run_comparison_experiment(
    eval_dataset_path="datasets/eval_questions.json",
    ground_truth_path="datasets/ground_truth.json",
    modes=["vanilla", "current", "full_self_rag"]
)
```

### 3. WandB에서 결과 확인

https://wandb.ai/your-team/lawbot-kr-evaluation

**주요 메트릭:**
- `eval_summary/{mode}/avg_recall_at_3`: 검색 품질
- `eval_summary/{mode}/avg_citation_f1`: 근거 법령 표시율
- `eval_summary/{mode}/avg_faithfulness`: 답변 충실도
- `eval_summary/{mode}/avg_response_time_ms`: 응답 시간

---

## 📊 평가 메트릭 설명

### Retrieval Metrics (검색 품질)
- **Recall@3**: 상위 3개 결과에 정답 포함 비율
- **MRR**: 첫 정답 문서의 역순위 평균
- **NDCG@3**: 순위를 고려한 검색 품질

### Citation Metrics (근거 법령 표시)
- **Precision**: 인용한 법령 중 정답 비율
- **Recall**: 정답 법령 중 인용한 비율
- **F1**: Precision과 Recall의 조화평균

### Answer Quality (답변 품질, LLM 평가)
- **Faithfulness**: 검색 결과 기반 답변 여부 (0-1)
- **Relevance**: 질문과의 관련성 (0-1)
- **Completeness**: 답변 완성도 (0-1)

### Cost & Latency
- **Response Time**: 응답 시간 (ms)
- **Total Tokens**: 총 토큰 사용량
- **API Calls**: 법령 API 호출 횟수

---

## 📈 데이터셋 확장 계획

**현재:** 10개 질문 (카테고리별 분포)
- specific_article: 5개
- situation: 5개

**목표:** 100개 질문
- 난이도별 균등 분포 (easy 30, medium 40, hard 30)
- 법령 분야별 분포 (민법 20, 형법 10, 근로 30, 행정 20, 기타 20)

**추가 방법:**
1. 실제 사용자 질문 로그에서 추출
2. 법령별 대표 조문 선정
3. GPT-5로 질문 생성 후 수동 검증
