# WandB 로깅 전략 (v2.0)

## 📊 세션 기반 로깅 구조

### 계층 구조
```
Project: lawbot-kr
  └─ Group: daily_20251211 (날짜별 자동 그룹화)
      ├─ Run: session-1702345678_143022 (사용자 A의 세션)
      │   ├─ Step 1: 질문1 → 답변1
      │   ├─ Step 2: 질문2 → 답변2
      │   └─ Step 3: 질문3 → 답변3
      │
      └─ Run: session-1702345789_144530 (사용자 B의 세션)
          ├─ Step 1: 질문1 → 답변1
          └─ Step 2: 질문2 → 답변2
```

## 🎯 핵심 개념

### 1. Group (날짜별)
- **형식**: `daily_YYYYMMDD`
- **예시**: `daily_20251211`
- **목적**: 날짜별 트렌드 분석, 시계열 비교
- **생성**: 자동 (매일 자정마다 새 그룹)

### 2. Run (세션별)
- **형식**: `{session_id}_{HHMMSS}`
- **예시**: `session-1702345678_143022`
- **목적**: 사용자별 대화 흐름 추적
- **생성**: 프론트엔드에서 세션 시작 시
- **종료**: 브라우저 닫기 또는 세션 만료

### 3. Step (대화 턴별)
- **형식**: 정수 (1, 2, 3, ...)
- **목적**: 세션 내 대화 진행도 추적
- **증가**: 새 질문마다 자동 증가

## 🔧 구현 방법

### 프론트엔드 (세션 ID 생성)
```typescript
// frontend/src/components/ChatInterface.tsx
const [sessionId] = useState(`session-${Date.now()}`);
```

### 백엔드 (세션별 Run 생성)
```python
# backend/src/monitoring/wandb_logger.py
logger = get_wandb_logger(session_id="session-1702345678")

# 자동으로 생성됨:
# - Group: daily_20251211
# - Run: session-1702345678_143022
# - Step: 0 (시작)
```

### 대화 턴마다 Step 증가
```python
# AgenticRAG.run() 호출 시
logger.increment_step()  # Step 1, 2, 3, ...
```

## 📈 로깅 메트릭

### 세션 레벨 (Run 전체)
- `session/total_conversations`: 총 대화 수
- `session/duration_minutes`: 세션 지속 시간
- `session/avg_response_time`: 평균 응답 시간

### 대화 레벨 (Step별)
- `conversation/execution_time`: 실행 시간
- `conversation/tool_calls_count`: 도구 호출 횟수
- `conversation/answer_length`: 답변 길이
- `conversation/user_satisfaction`: 사용자 만족도 (추후 추가)

### 도구 레벨
- `tool/vector_search/latency`: 벡터 검색 시간
- `tool/vector_search/similarity`: 유사도 점수
- `tool/law_api/response_time`: API 응답 시간

## 🎨 활용 예시

### 1. 날짜별 트렌드 분석
```python
# WandB UI에서
Group: daily_20251211
  → Run 100개 (동시 사용자 100명)
  → 평균 응답 시간: 3.2초
  → 가장 많이 검색된 법령: 근로기준법 제56조
```

### 2. 사용자 경험 분석
```python
# 특정 세션 분석
Run: session-abc123_143022
  → Step 1: "야근수당" → 2.1초 (성공)
  → Step 2: "택배 분실" → 3.5초 (성공)
  → Step 3: "부당해고" → 2.8초 (성공)
  → 평균: 2.8초, 성공률 100%
```

### 3. A/B 테스트
```python
# Group: daily_20251211
#   Tag: experiment-a (기존 방식)
#   Tag: experiment-b (새 방식)
# → 평균 응답 시간 비교
```

## 🚨 주의사항

### 세션 종료 처리
세션이 종료되면 반드시 WandB run을 종료해야 합니다:

```python
from src.monitoring import cleanup_wandb_logger

# 세션 종료 시
cleanup_wandb_logger(session_id)
```

**문제**: 브라우저를 닫아도 백엔드는 세션 종료를 모름
**해결**:
1. 프론트엔드에서 `beforeunload` 이벤트로 `/session/end` 엔드포인트 호출
2. 또는 세션 타임아웃 (30분 무활동 시 자동 종료)

### 메모리 관리
```python
# 세션이 너무 많아지면 메모리 사용량 증가
# 최대 100개 세션까지만 유지하도록 제한 (추후 구현)
```

## 📊 예상 Run 수

| 기간 | 동시 사용자 | Run 수 | 비고 |
|------|------------|--------|------|
| 1시간 | 10명 | 10개 | 적당함 |
| 1일 | 100명 | 100개 | 적당함 |
| 1주 | 700명 | 700개 | 관리 가능 |
| 1달 | 3,000명 | 3,000개 | 관리 가능 |

✅ **결론**: 세션 기반 로깅은 적당한 run 수를 유지하면서도 충분한 분석 가능

## 🔄 버전별 비교

| 항목 | v1.0 (단일 Run) | v2.0 (세션별 Run) |
|------|----------------|------------------|
| Run 수 | 1개 (전체 기간) | ~100개/일 |
| 분석 깊이 | 얕음 | 깊음 (사용자별) |
| 트렌드 추적 | 불가능 | 가능 (날짜별 Group) |
| 사용자 흐름 | 불가능 | 가능 (Step 추적) |
| 메모리 사용 | 낮음 | 중간 |
| 관리 복잡도 | 낮음 | 중간 |

## 🎯 다음 단계

1. **세션 타임아웃 구현** (30분 무활동 시 자동 종료)
2. **프론트엔드 세션 종료 이벤트** (`beforeunload`)
3. **사용자 만족도 수집** (별점, 피드백)
4. **대시보드 구축** (Streamlit 또는 WandB custom plots)
