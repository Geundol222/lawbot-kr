# 평가 스크립트

## 📁 파일 구조

```
scripts/
├── collect_retrieval_results.py  # 검색 결과 수집 (재현성 확보)
└── README.md                      # 이 문서
```

---

## 🎯 `collect_retrieval_results.py`

### 목적

평가 데이터셋의 **모든 질문에 대해 검색 결과를 미리 수집**하여 Ground Truth에 저장합니다.

**왜 필요한가?**
1. ✅ **재현성 확보**: 매번 같은 검색 결과 사용 → 공정한 비교
2. ✅ **순수 생성 능력 평가**: Vanilla vs Self-RAG 차이를 "답변 생성" 능력만 비교
3. ✅ **실험 시간 단축**: 검색 건너뛰고 바로 생성

---

## 🚀 사용법

### 1. 기본 사용 (10개 질문)

```bash
cd e:\AI_Project\lawbot-kr
python scripts/collect_retrieval_results.py
```

**출력:**
```
============================================================
🔍 검색 결과 수집 시작
============================================================

📦 VectorSearch 초기화 중...
✅ 총 10개 질문에 대해 검색 결과 수집

검색 중: 100%|██████████| 10/10 [00:30<00:00,  3.00s/it]
✅ q001: 5개 문서 수집
   Top 1: 민법 750 (유사도: 0.923)
✅ q002: 5개 문서 수집
   Top 1: 근로기준법 56 (유사도: 0.887)
...

💾 Ground Truth 저장 중: datasets/ground_truth.json

============================================================
✅ 검색 결과 수집 완료!
============================================================
수집 완료: 10개
건너뜀: 0개
총 10개 질문
```

---

### 2. 옵션 지정

```bash
# Top-k 변경 (기본: 5)
python scripts/collect_retrieval_results.py --top_k 10

# 파일 경로 지정
python scripts/collect_retrieval_results.py \
    --eval_questions datasets/eval_questions_100.json \
    --ground_truth datasets/ground_truth_100.json
```

---

### 3. 검증만 수행

```bash
# 이미 수집된 결과 검증
python scripts/collect_retrieval_results.py --verify
```

**출력:**
```
============================================================
🔍 검색 결과 검증
============================================================

총 질문: 100개
검색 결과 있음: 95개
검색 결과 없음 (빈 리스트): 5개
검색 결과 미수집: 0개

⚠️  경고: 5개 질문의 검색 결과가 비어있습니다.
   threshold를 낮추거나 질문을 수정하세요.
```

---

## 📊 Ground Truth 구조 (수집 후)

```json
{
  "q001": {
    "articles": ["민법 750"],
    "context": "민법 제750조는 불법행위로 인한 손해배상 책임...",
    "expected_keywords": ["불법행위", "손해배상", "고의", "과실"],

    "retrieved_docs": [
      {
        "law_name": "민법",
        "article": "750",
        "content": "고의 또는 과실로 인한 위법행위로 타인에게 손해를 가한 자는...",
        "similarity": 0.923,
        "score": 0.923
      },
      {
        "law_name": "민법",
        "article": "751",
        "content": "타인의 신체, 자유 또는 명예를 해하거나...",
        "similarity": 0.782,
        "score": 0.782
      }
    ]
  }
}
```

---

## 🔄 워크플로우

### Step 1: 평가 질문 작성

```bash
# datasets/eval_questions.json 편집
# 10개 → 100개로 확장
```

### Step 2: Ground Truth 레이블링

```bash
# datasets/ground_truth.json 편집
# articles, context, expected_keywords 추가
```

### Step 3: 검색 결과 수집 (이 스크립트)

```bash
python scripts/collect_retrieval_results.py
```

### Step 4: 평가 실행

```bash
cd backend
python -m src.monitoring.evaluator
```

**평가 시 동작:**
- Ground Truth에 `retrieved_docs` 있으면 **재현성 모드** (고정된 검색 결과 사용)
- 없으면 **일반 모드** (실시간 검색)

---

## 💡 재현성 문제 해결

### 문제: 검색 결과가 매번 달라짐

**원인:**
1. LLM 서브쿼리 추출 (비결정적)
2. 멀티스레드 병렬 검색 (완료 순서 랜덤)
3. 병합/재순위 순서 (입력 순서 의존)

**해결:**
- ✅ **검색 결과 고정 (이 스크립트)**
- ❌ Random seed 고정 (의미 없음)
- ⚠️ Deterministic 모드 (복잡하고 느림)

---

## 📈 실험 비교 예시

### 재현성 없이 (문제)

```python
# 실험 1
Vanilla RAG: Recall@3 = 0.75 (retrieved_docs: [민법 750, 751, 752])

# 실험 2 (같은 질문, 다시 실행)
Vanilla RAG: Recall@3 = 0.68 (retrieved_docs: [민법 750, 752, 753])  # 다름!
```

→ **공정한 비교 불가능**

---

### 재현성 확보 (해결)

```python
# Ground Truth에 retrieved_docs 고정
"q001": {
  "retrieved_docs": [민법 750, 751, 752]  # 고정!
}

# 실험 1
Vanilla RAG: Citation F1 = 0.75 (고정된 docs 사용)

# 실험 2
Self-RAG: Citation F1 = 0.88 (동일한 고정 docs 사용)
```

→ **공정한 비교 가능!** (차이는 순수하게 생성 능력)

---

## ⚠️ 주의사항

1. **DB 변경 시 재수집 필요**
   - 임베딩 재생성 후 검색 결과가 달라질 수 있음
   - 재수집 시 `--verify` 먼저 실행해서 기존 결과 확인

2. **빈 검색 결과 처리**
   - 일부 질문은 threshold 미달로 결과 없을 수 있음
   - `--verify`로 확인 후 질문 수정 또는 threshold 조정

3. **실행 시간**
   - 100개 질문 × 3초 = **약 5분**
   - 네트워크/DB 상태에 따라 변동

---

## 🔧 트러블슈팅

### Q1: "검색 결과 없음" 경고가 많이 나옴

**A:** Threshold를 낮추거나 질문을 명확하게 수정하세요.

```python
# vector_search.py에서 threshold 조정
results = vector_search.search(question, top_k=5, threshold=0.0)  # 0.7 → 0.0
```

### Q2: 이미 수집된 결과를 덮어쓰고 싶음

**A:** Ground Truth에서 `retrieved_docs` 필드를 삭제하거나, 스크립트 수정:

```python
# collect_retrieval_results.py:67 주석 처리
# if qid in ground_truth and "retrieved_docs" in ground_truth[qid]:
#     print(f"⏭️  {qid}: 이미 검색 결과 존재 (건너뜀)")
#     skipped_count += 1
#     continue
```

### Q3: 특정 질문만 재수집하고 싶음

**A:** Ground Truth에서 해당 질문의 `retrieved_docs` 삭제 후 재실행

```json
{
  "q005": {
    "articles": ["민법 628"],
    // "retrieved_docs": [...]  // 이 줄 삭제
  }
}
```

---

## 📚 관련 파일

- `datasets/eval_questions.json` - 평가 질문 세트
- `datasets/ground_truth.json` - 정답 + 검색 결과
- `backend/src/monitoring/evaluator.py` - 평가 실행기
- `backend/src/embeddings/vector_search.py` - 벡터 검색
