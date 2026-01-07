# 검색 품질 개선 계획

## 실패 사례 심층 분석

### 🔴 Case 1: q001 "민법 제750조가 뭐야?"

**문제**:
- Ground Truth: `민법 750`
- 검색 결과: 민법 785조, 780조, 795조... (모두 삭제된 조문)
- **Recall@10 = 0.00** (완전 실패)

**원인 분석**:
1. **직접 조문 질문 패턴 미감지**
   - "민법 제750조"라는 명확한 조문 번호가 있음
   - 현재는 semantic 검색으로만 처리 → 삭제된 유사 조문이 상위 노출

2. **벡터 유사도 한계**
   - 질문: "민법 제750조가 뭐야?"
   - 삭제된 조문들: "제785조 삭제 <2005.3.31>" (내용이 짧아서 높은 유사도)
   - 실제 750조: 불법행위 관련 긴 내용 → 상대적으로 낮은 유사도

**개선 방안**:
```python
# 우선순위 1: 직접 조문 질문 감지 및 처리
def detect_direct_article_query(query: str) -> Optional[Dict]:
    """
    "○○법 제XX조" 패턴 감지 → 직접 DB 조회

    예시:
        "민법 제750조가 뭐야?" → {"law": "민법", "article": "750"}
        "근로기준법 56조는?" → {"law": "근로기준법", "article": "56"}
    """
    pattern = r'([가-힣]+(?:법|령|규칙|조례))\s*제?\s*(\d+)\s*조'
    match = re.search(pattern, query)
    if match:
        law_name = match.group(1)
        article_num = match.group(2)
        return {"law": law_name, "article": article_num}
    return None

# search_vector_db 함수 시작 부분에 추가
direct_query = detect_direct_article_query(query)
if direct_query:
    # Supabase에서 정확히 매칭되는 조문 우선 검색
    exact_result = supabase.table("law_cache")\
        .select("*")\
        .eq("law_name", direct_query["law"])\
        .eq("article", f"제{direct_query['article']}조")\
        .execute()

    if exact_result.data:
        # 정확한 조문을 최우선으로 반환
        return format_exact_match_result(exact_result.data[0])
```

**예상 효과**:
- q001 Recall: 0.00 → 1.00
- q004, q007, q008 등 직접 조문 질문의 정확도 향상

---

### 🔴 Case 2: q005 "월세 계약을 중도 해지하고 싶은데 보증금을 돌려받을 수 있어?"

**문제**:
- Ground Truth: `민법 628`, `주택임대차보호법 6`
- **Recall@10 = 0.00** (완전 실패)

**원인 분석**:
1. **키워드 미스매치**
   - 질문: "월세", "중도 해지", "보증금"
   - 실제 조문: "차임", "계약의 갱신", "임대차"
   - Semantic 검색으로는 연결되지 않음

2. **법률 용어 vs 일상 용어 갭**
   - 사용자: "월세" → 법령: "차임"
   - 사용자: "중도 해지" → 법령: "계약의 갱신", "해지"

**개선 방안**:
```python
# 우선순위 2: 법률 용어 동의어 사전
LAW_SYNONYMS = {
    "월세": ["차임", "임대료", "임차료"],
    "전세": ["임대차", "보증금"],
    "집주인": ["임대인", "임대차"],
    "세입자": ["임차인"],
    "해고": ["면직", "파면", "해임", "정리해고"],
    "손해배상": ["배상책임", "불법행위"],
    "계약해지": ["해지", "해제", "중도해지"],
}

def expand_with_law_terms(query: str) -> str:
    """
    사용자 질문의 일상 용어를 법률 용어로 확장

    예시:
        "월세 계약을 중도 해지"
        → "월세 차임 임대료 계약을 중도 해지 계약해지 해지"
    """
    expanded_terms = []
    words = query.split()

    for word in words:
        expanded_terms.append(word)
        if word in LAW_SYNONYMS:
            expanded_terms.extend(LAW_SYNONYMS[word])

    return " ".join(expanded_terms)
```

**BM25 가중치 강화**:
```python
# 현재: Semantic + BM25 단순 병합
# 개선: 가중 평균으로 키워드 매칭 강화

def merge_with_weighted_score(semantic_results, bm25_results):
    """
    Semantic: 0.6, BM25: 0.4 가중치로 병합
    """
    for item in merged_items:
        semantic_score = item.get("semantic_score", 0) or 0
        bm25_score = item.get("bm25_score", 0) or 0

        # 가중 평균
        item["final_score"] = semantic_score * 0.6 + bm25_score * 0.4

    return sorted(merged_items, key=lambda x: x["final_score"], reverse=True)
```

**예상 효과**:
- q005 Recall: 0.00 → 0.50~1.00
- 일상 용어 질문의 검색 성공률 향상

---

### 🔴 Case 3: q006 "교통사고로 다쳤을 때 보상은 어떻게 받아?"

**문제**:
- Ground Truth: `민법 750`, `자동차손해배상 보장법 3`
- **Recall@10 = 0.00** (완전 실패)

**원인 분석**:
1. **멀티홉 추론 필요**
   - "교통사고" → "자동차" 연결
   - "보상" → "손해배상", "배상책임" 연결
   - 2단계 추론이 필요하지만 벡터 검색은 1-hop만 처리

2. **도메인 특화 법률 누락**
   - "교통사고"는 일반적인 키워드
   - 하지만 "자동차손해배상 보장법"이라는 특수 법령이 필요
   - 벡터 DB에 해당 법령이 없거나 임베딩이 약함

**개선 방안**:
```python
# 우선순위 3: Query Decomposition (질문 분해)
def decompose_complex_query(query: str, llm) -> List[str]:
    """
    복잡한 질문을 여러 하위 질문으로 분해

    예시:
        "교통사고로 다쳤을 때 보상은 어떻게 받아?"
        → [
            "교통사고 손해배상 책임",
            "자동차 사고 피해자 보상",
            "불법행위 손해배상"
        ]
    """
    prompt = f"""다음 법률 질문을 2-3개의 하위 질문으로 분해하세요.
각 하위 질문은 법률 검색에 최적화되어야 합니다.

질문: {query}

JSON 배열로 반환:"""

    response = llm_invoke_with_retry(llm, prompt)
    subqueries = json.loads(response.content)

    return subqueries

# 각 하위 질문으로 검색 후 병합
all_results = []
for subquery in subqueries:
    results = vector_search(subquery, top_k=5)
    all_results.extend(results)

# 중복 제거 및 Rerank
final_results = rerank(query, deduplicate(all_results), top_k=10)
```

**도메인 법령 우선순위 부스팅**:
```python
# 특정 상황에서 특수 법령 우선 검색
SITUATION_TO_LAW_MAP = {
    "교통사고": ["자동차손해배상 보장법", "민법"],
    "임대차": ["주택임대차보호법", "상가건물 임대차보호법", "민법"],
    "근로": ["근로기준법", "최저임금법", "산업안전보건법"],
}

def boost_domain_laws(results, query, boost_factor=1.3):
    """
    특정 상황에 해당하는 법령의 점수를 부스팅
    """
    for keyword, laws in SITUATION_TO_LAW_MAP.items():
        if keyword in query:
            for result in results:
                if result["law_name"] in laws:
                    result["score"] *= boost_factor

    return sorted(results, key=lambda x: x["score"], reverse=True)
```

**예상 효과**:
- q006 Recall: 0.00 → 0.50~1.00
- 복잡한 상황 질문의 검색 성공률 향상

---

### 🔴 Case 4: q009 "근로기준법 별표 1에서 정한 업종은 뭐야?"

**문제**:
- Ground Truth: `근로기준법 별표1`
- **Recall@10 = 0.00** (완전 실패)

**원인 분석**:
1. **별표/부칙 데이터 누락**
   - 현재 law_cache는 "조문" 단위만 저장
   - "별표", "부칙"은 별도 테이블 또는 필드에 저장되어야 함
   - 벡터 검색 대상에 포함되지 않음

2. **데이터 수집 문제**
   - Law.go.kr API가 별표를 별도로 제공
   - 현재 크롤러가 별표를 수집하지 않음

**개선 방안**:
```python
# 우선순위 4: 별표/부칙 데이터 수집 및 인덱싱

# 1. 데이터 수집
def fetch_law_appendices(law_name: str):
    """
    법령의 별표, 부칙, 서식 등을 추가 수집
    """
    # Law.go.kr API에서 별표 조회
    response = requests.get(
        LAW_API_SERVICE,
        params={
            "OC": LAW_API_OC,
            "target": "byeol",  # 별표 조회
            "MST": get_law_mst(law_name),
        }
    )
    return parse_appendices(response)

# 2. DB 스키마 확장
"""
ALTER TABLE law_cache ADD COLUMN appendix_type TEXT;
-- appendix_type: "article" | "byeol" | "附則" | "서식"

CREATE INDEX idx_appendix_type ON law_cache(appendix_type);
"""

# 3. 별표 질문 감지
def detect_appendix_query(query: str) -> Optional[str]:
    """
    별표/부칙 질문 패턴 감지
    """
    patterns = [
        r'별표\s*(\d+)',
        r'부칙',
        r'서식\s*(\d+)',
    ]

    for pattern in patterns:
        if re.search(pattern, query):
            return "byeol"  # appendix_type
    return None
```

**예상 효과**:
- q009 Recall: 0.00 → 1.00
- 별표/부칙 관련 질문 처리 가능

---

## 개선 우선순위 및 구현 계획

### Phase 1: Quick Wins (1-2일)

#### ✅ 1.1 직접 조문 질문 감지 (높은 효과, 낮은 난이도)
- **구현**: `detect_direct_article_query()` 함수 추가
- **적용 위치**: `search_vector_db()` 시작 부분
- **예상 개선**: q001, q004, q007, q008 → Recall 0.00 → 1.00
- **영향도**: 4/10 질문 (40%)

#### ✅ 1.2 법률 용어 동의어 확장 (중간 효과, 낮은 난이도)
- **구현**: `LAW_SYNONYMS` 사전 + `expand_with_law_terms()`
- **적용 위치**: Query Expansion 단계
- **예상 개선**: q005 → Recall 0.00 → 0.50
- **영향도**: 2/10 질문 (20%)

#### 📊 Phase 1 예상 결과
- Recall@3: 0.35 → **0.55** (+20%p)
- Recall@5: 0.45 → **0.65** (+20%p)
- Recall@10: 0.50 → **0.70** (+20%p)

### Phase 2: Medium Improvements (3-5일)

#### 🔧 2.1 BM25 가중치 조정
- **구현**: `merge_with_weighted_score()`
- **가중치**: Semantic 0.6, BM25 0.4
- **예상 개선**: 키워드 중심 질문 성능 향상

#### 🔧 2.2 Query Decomposition
- **구현**: `decompose_complex_query()`
- **LLM 사용**: Gemini Flash Lite
- **예상 개선**: q006 → Recall 0.00 → 0.50
- **영향도**: 1/10 질문 (10%)

#### 🔧 2.3 도메인 법령 부스팅
- **구현**: `SITUATION_TO_LAW_MAP` + `boost_domain_laws()`
- **예상 개선**: 상황별 질문 정확도 향상

#### 📊 Phase 2 예상 결과
- Recall@3: 0.55 → **0.65** (+10%p)
- Recall@5: 0.65 → **0.75** (+10%p)
- Recall@10: 0.70 → **0.80** (+10%p)

### Phase 3: Long-term Improvements (1-2주)

#### 🚀 3.1 별표/부칙 데이터 수집
- **구현**: 크롤러 확장, DB 스키마 변경
- **데이터 증가**: 8,182 조문 → ~10,000 (별표/부칙 포함)
- **예상 개선**: q009 → Recall 0.00 → 1.00

#### 🚀 3.2 Reranker Fine-tuning
- **데이터셋**: Ground Truth 질문-조문 쌍
- **모델**: BGE Reranker 법률 도메인 Fine-tuning
- **예상 개선**: 전체 Recall +5~10%p

#### 🚀 3.3 Embedding Model 교체/Fine-tuning
- **후보 모델**:
  - `BAAI/bge-m3` (다국어, 법률 도메인 적합)
  - `intfloat/e5-large-v2` Fine-tuned on Korean Law
- **예상 개선**: Semantic 검색 정확도 +10~15%p

#### 📊 Phase 3 예상 결과
- Recall@3: 0.65 → **0.80** (+15%p)
- Recall@5: 0.75 → **0.90** (+15%p)
- Recall@10: 0.80 → **0.95** (+15%p)

---

## Citation F1 개선 계획

### 현재 문제
- **Citation F1 = 0.30** (매우 낮음)
- 검색은 성공했지만 답변에 조문 번호를 명시하지 않음

### 개선 방안

#### ✅ 1. 답변 생성 프롬프트 강화 (즉시 적용)

**현재 프롬프트**:
```
위 메시지에서 도구(tool)가 전달한 법령/판례 정보를 바탕으로 답변을 작성하세요.
```

**개선 프롬프트**:
```
위 메시지에서 도구(tool)가 전달한 법령/판례 정보를 바탕으로 답변을 작성하세요.

**필수 준수 사항**:
1. 답변에 인용한 모든 조문은 반드시 "○○법 제XX조"라고 명시하세요.
2. 조문 내용을 설명할 때는 반드시 조문 번호를 먼저 언급하세요.
   예시: "근로기준법 제56조에 따르면, 연장근로에 대해 통상임금의 50% 이상을 가산..."

잘못된 예시: "연장근로에 대해 50% 이상 가산됩니다."
올바른 예시: "근로기준법 제56조에 따라 연장근로에 대해 통상임금의 50% 이상을 가산합니다."
```

#### ✅ 2. 구조화된 답변 포맷 (중간 적용)

```python
ANSWER_TEMPLATE = """
## 관련 법령

{citations}

## 답변

{content}

## 참고 판례

{precedents}
"""

def format_structured_answer(citations, content, precedents):
    """
    구조화된 답변 형식으로 강제
    """
    citation_list = "\n".join([
        f"- **{law} 제{article}조**"
        for law, article in citations
    ])

    return ANSWER_TEMPLATE.format(
        citations=citation_list,
        content=content,
        precedents=precedents
    )
```

#### ✅ 3. Post-processing 검증 (즉시 적용)

```python
def validate_citations(answer: str, retrieved_docs: List[Dict]) -> str:
    """
    답변에 조문 번호가 누락되었는지 검증하고 추가
    """
    # 답변에서 인용된 조문 추출
    cited_articles = extract_citations_from_answer(answer)

    # 검색된 조문 중 인용되지 않은 것 찾기
    missing_citations = []
    for doc in retrieved_docs[:3]:  # Top-3만 체크
        law_article = f"{doc['law_name']} 제{doc['article']}조"
        if law_article not in cited_articles:
            missing_citations.append(law_article)

    # 누락된 조문이 있으면 답변 끝에 추가
    if missing_citations:
        footer = "\n\n**참고 조문**: " + ", ".join(missing_citations)
        return answer + footer

    return answer
```

#### 📊 Citation 개선 예상 결과
- Citation F1: 0.30 → **0.70~0.80** (+40~50%p)

---

## 구현 우선순위 (권장)

### 🔥 즉시 구현 (오늘~내일)
1. ✅ 직접 조문 질문 감지 (`detect_direct_article_query`)
2. ✅ Citation 프롬프트 강화
3. ✅ Citation Post-processing 검증

**예상 개선**: Recall +20%p, Citation F1 +40%p

### 🚀 이번 주 구현
4. 법률 용어 동의어 사전 (`LAW_SYNONYMS`)
5. BM25 가중치 조정 (`merge_with_weighted_score`)

**예상 개선**: Recall +10%p

### 📅 다음 주 구현
6. Query Decomposition (`decompose_complex_query`)
7. 도메인 법령 부스팅 (`boost_domain_laws`)

**예상 개선**: Recall +10%p

### 🔮 장기 과제 (2주 이상)
8. 별표/부칙 데이터 수집
9. Reranker Fine-tuning
10. Embedding Model Fine-tuning

**예상 개선**: Recall +15~20%p

---

## 성능 목표

| Phase | Recall@3 | Recall@5 | Recall@10 | Citation F1 |
|-------|----------|----------|-----------|-------------|
| **현재** | 0.35 | 0.45 | 0.50 | 0.30 |
| **Phase 1** | 0.55 | 0.65 | 0.70 | 0.70 |
| **Phase 2** | 0.65 | 0.75 | 0.80 | 0.75 |
| **Phase 3** | 0.80 | 0.90 | 0.95 | 0.80 |

**최종 목표**: Recall@5 = **90%**, Citation F1 = **80%**

---

## 다음 액션 아이템

1. [ ] 직접 조문 질문 감지 구현
2. [ ] Citation 프롬프트 개선
3. [ ] Citation Post-processing 추가
4. [ ] Phase 1 개선 후 재평가 실행
5. [ ] 결과 비교 및 다음 단계 결정

