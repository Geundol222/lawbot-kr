# Buffer Memory (대화 맥락 유지)

## 개요

Buffer Memory는 같은 세션 내에서 이전 대화를 기억하고 맥락을 유지하는 기능입니다. 사용자가 "그거", "그럼", "추가로" 등의 표현으로 이전 질문을 참조할 수 있도록 합니다.

## 구현 아키텍처

```
┌─────────────────────────────────────────────────────────┐
│ AgenticRAG                                              │
│  └─ ConversationMemory (session-based)                 │
│      ├─ In-memory buffer (최근 5턴)                      │
│      └─ Supabase integration (영구 저장)                │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 대화 흐름                                                │
│                                                         │
│ 1. 새 질문 입력                                         │
│ 2. 이전 대화 이력 로드 (from Memory)                    │
│ 3. [이전 대화 + 현재 질문] → LLM                        │
│ 4. LLM 답변 생성 (맥락 고려)                            │
│ 5. 대화 저장 (Memory + Supabase)                        │
└─────────────────────────────────────────────────────────┘
```

## 주요 컴포넌트

### 1. ConversationMemory (기본 클래스)

**파일**: [backend/src/memory/conversation_memory.py](../backend/src/memory/conversation_memory.py)

**기능**:
- 세션별 대화 이력 관리
- 메시지 추가/조회
- 자동 메시지 트리밍 (최대 N턴 유지)
- 텍스트 컨텍스트 변환

**주요 메서드**:

```python
class ConversationMemory:
    def __init__(self, session_id: str, max_messages: int = 10)

    def add_user_message(self, content: str)
    def add_ai_message(self, content: str)

    def get_messages(self) -> List[BaseMessage]
    def get_context_string(self) -> str

    def clear(self)
```

### 2. SupabaseConversationMemory (DB 연동)

**기능**:
- ConversationMemory 확장
- Supabase DB 저장/로드
- 세션 재시작 시 이전 대화 자동 로드
- 세션 생성 (foreign key 제약조건 처리)

**주요 메서드**:

```python
class SupabaseConversationMemory(ConversationMemory):
    def __init__(self, session_id: str, supabase_client,
                 max_messages: int = 10, load_previous: bool = True)

    def _load_previous_conversations(self)

    def add_and_save(self, user_question: str, bot_answer: str,
                     law_name: Optional[str] = None,
                     article: Optional[str] = None,
                     response_time_ms: Optional[int] = None)
```

### 3. AgenticRAG 통합

**파일**: [backend/src/agentic_rag.py](../backend/src/agentic_rag.py)

**통합 지점**:

```python
class AgenticRAG:
    def __init__(self, session_id: Optional[str] = None,
                 mode: str = "current",
                 use_memory: bool = True):  # ← 기본 활성화

        # 메모리 초기화
        if use_memory:
            self.memory = create_conversation_memory(
                session_id=self.session_id,
                supabase_client=supabase,
                max_turns=5,  # 최근 5턴만 유지
                load_previous=True  # 이전 대화 불러오기
            )
        else:
            self.memory = None
```

**답변 생성 시 메모리 활용**:

```python
# Vanilla 모드 (agentic_rag.py:818-824)
messages = [SystemMessage(...)]

# 이전 대화 이력 추가
if self.memory:
    previous_messages = self.memory.get_messages()
    messages.extend(previous_messages)

# 현재 질문 추가
messages.append(HumanMessage(content=f"질문: {question}..."))
```

**대화 저장** ([agentic_rag.py:746-762](../backend/src/agentic_rag.py#L746-L762)):

```python
# 메모리에 대화 저장
if self.memory and hasattr(self.memory, 'add_and_save'):
    law_name = retrieved_docs[0].get("law_name") if retrieved_docs else None
    article = retrieved_docs[0].get("article") if retrieved_docs else None

    self.memory.add_and_save(
        user_question=question,
        bot_answer=answer,
        law_name=law_name,
        article=article,
        response_time_ms=response_time_ms
    )
```

### 4. AgentStreaming 통합

**파일**: [backend/src/agent_streaming.py](../backend/src/agent_streaming.py)

**스트리밍 답변에도 메모리 적용**:

```python
# agent_streaming.py:70-76
# 이전 대화 이력 추가 (메모리가 있으면)
if self.memory:
    previous_messages = self.memory.get_messages()
    initial_messages.extend(previous_messages)

# 현재 질문 추가
initial_messages.append(HumanMessage(content=question))
```

## 데이터 흐름

### 1. 첫 번째 대화 (새 세션)

```
사용자: "민법 제750조가 뭐야?"
                ↓
┌───────────────────────────────────┐
│ AgenticRAG 초기화                  │
│  - session_id 생성                │
│  - memory 초기화 (빈 상태)         │
└───────────────────────────────────┘
                ↓
┌───────────────────────────────────┐
│ 답변 생성                          │
│  - 이전 대화: 없음                 │
│  - 검색 → LLM → 답변              │
└───────────────────────────────────┘
                ↓
┌───────────────────────────────────┐
│ 메모리 저장                        │
│  1. In-memory buffer 저장         │
│     - HumanMessage("민법...")     │
│     - AIMessage("민법 제750조는...") │
│  2. Supabase DB 저장              │
│     - conversation_logs 테이블    │
└───────────────────────────────────┘
```

### 2. 두 번째 대화 (같은 세션)

```
사용자: "그럼 손해배상은 얼마나 받을 수 있어?"
                ↓
┌───────────────────────────────────┐
│ AgenticRAG 초기화                  │
│  - 동일 session_id                │
│  - memory 초기화                  │
│    → DB에서 이전 대화 로드 ✅      │
│      (Q: 민법 제750조가 뭐야?)     │
│      (A: 민법 제750조는...)       │
└───────────────────────────────────┘
                ↓
┌───────────────────────────────────┐
│ 답변 생성                          │
│  - 이전 대화: 1턴 (2개 메시지) ✅  │
│  - LLM에게 전달:                  │
│    [이전Q, 이전A, 현재Q]          │
│  - LLM이 맥락 이해하여 답변       │
└───────────────────────────────────┘
                ↓
┌───────────────────────────────────┐
│ 메모리 저장                        │
│  1. In-memory buffer 업데이트     │
│     - 총 4개 메시지 (2턴)         │
│  2. Supabase DB 저장              │
│     - 2턴째 대화 추가             │
└───────────────────────────────────┘
```

## 메모리 관리

### 메모리 제한

**설정**: `max_turns=5` (최근 5턴 = 10개 메시지)

**이유**:
- LLM 컨텍스트 윈도우 효율 사용
- 응답 속도 유지
- 최신 대화에 집중

**동작**:
- 5턴 초과 시 오래된 대화부터 제거
- SystemMessage는 항상 유지

```python
def _trim_messages(self):
    """메시지 수 제한 (최신 N개만 유지)"""
    if len(self.messages) > self.max_messages:
        system_messages = [m for m in self.messages if isinstance(m, SystemMessage)]
        other_messages = [m for m in self.messages if not isinstance(m, SystemMessage)]

        # 최신 max_messages개만 유지
        other_messages = other_messages[-self.max_messages:]

        self.messages = system_messages + other_messages
```

### DB 저장 정책

**테이블**: `conversation_logs`

**저장 시점**: 답변 생성 완료 후 즉시 저장

**저장 데이터**:
- `session_id`: 세션 UUID
- `user_question`: 사용자 질문
- `bot_answer`: AI 답변
- `law_name`: 참조 법령명 (optional)
- `article`: 참조 조문 (optional)
- `response_time_ms`: 응답 시간 (optional)
- `created_at`: 생성 시각 (자동)

**Foreign Key 제약조건**:
- `session_id` → `sessions.session_id`
- 세션이 없으면 자동 생성

## 프롬프트 엔지니어링

### 시스템 프롬프트에 컨텍스트 인식 추가

**핵심 원칙**: 이전 대화 내용을 반복하지 않고, 새로운 정보에만 집중

[agent_streaming.py:188](../backend/src/agent_streaming.py#L188):

```python
system_message = """위 메시지에서 도구(tool)가 전달한 법령/판례 정보를 바탕으로 답변을 작성하세요.

**이전 대화가 있다면 맥락을 고려하여 답변하세요:**
- 사용자가 "그거", "그럼", "추가로" 등으로 이전 질문을 참조할 수 있습니다.
- **이미 설명한 내용은 반복하지 마세요. 새로운 질문에만 집중하세요.**
- 예: "주휴수당도 포함되는거야?" → "아니요, 별개입니다." (야근수당 재설명 불필요)
- 예: "그거 안 주면 어떻게 돼?" → "주휴수당을 안 주면 근로기준법 위반..." (야근수당/주휴수당 재설명 불필요)
"""
```

[agentic_rag.py:815](../backend/src/agentic_rag.py#L815) (Vanilla 모드도 동일한 지침 적용)

## 사용 예시

### 예시 1: 연속 질문

```
👤 사용자: "민법 제750조가 뭐야?"
🤖 AI: "민법 제750조는 불법행위의 가장 기본적인 원칙을 규정합니다..."

👤 사용자: "그럼 손해배상은 얼마나 받을 수 있어?"
              ↑ "그럼" = 이전 대화 참조
🤖 AI: "민법 제750조에 따른 손해배상액은..." ✅ 맥락 이해
```

### 예시 2: 추가 질문

```
👤 사용자: "야근수당은 얼마나 받을 수 있어?"
🤖 AI: "근로기준법 제56조에 따라 통상임금의 50% 가산..."

👤 사용자: "주휴수당도 포함되는거야?"
              ↑ "도" = 이전 야근수당 맥락
🤖 AI: "네, 주휴수당도 통상임금에 포함됩니다..." ✅ 맥락 이해
```

### 예시 3: 대명사 참조

```
👤 사용자: "근로기준법 제56조 알려줘"
🤖 AI: "근로기준법 제56조는 연장근로에 대한 가산임금 규정입니다..."

👤 사용자: "거기에 예외 조항 있어?"
              ↑ "거기" = 근로기준법 제56조
🤖 AI: "근로기준법 제56조의 예외 조항은..." ✅ 맥락 이해
```

## 테스트 결과

**테스트 파일**: [test_buffer_memory.py](../test_buffer_memory.py)

**테스트 시나리오**:

1. ✅ 첫 대화 - 메모리 없음 상태에서 시작
2. ✅ 메모리 저장 - In-memory + DB 저장 확인
3. ✅ 세션 재시작 - 새 Agent 인스턴스에서 이전 대화 로드
4. ✅ 맥락 유지 - "그럼" 참조하는 두 번째 질문 처리
5. ✅ DB 확인 - Supabase에 2턴 저장 확인

**테스트 결과**:

```
🎉 Buffer Memory 통합 테스트 성공!

확인된 기능:
  ✅ 대화 메모리 저장 (in-memory)
  ✅ Supabase DB 저장
  ✅ 이전 대화 로드 (세션 재시작 시)
  ✅ 맥락 유지 (연속 대화)
```

## 성능 고려사항

### 메모리 오버헤드

- In-memory: 최대 10개 메시지 (negligible)
- DB 쿼리: 세션 시작 시 1회 (SELECT ... LIMIT 5)
- 저장: 답변 완료 시 1회 (INSERT)

### 응답 속도 영향

- 이전 대화 로드: ~100ms (Supabase RPC)
- LLM 컨텍스트 증가: 5턴 × ~200 토큰 = ~1000 토큰 추가
- 전체 응답 시간 증가: < 5%

### 컨텍스트 윈도우 관리

- Gemini 2.0 Flash: 1M 토큰 컨텍스트
- 5턴 대화: ~2000 토큰 (0.2%)
- 여유 충분 ✅

## 향후 개선 사항

### 1. 세션 요약 (Session Summary)

- 10턴 초과 시 이전 대화 요약
- 요약본을 컨텍스트로 유지
- 토큰 효율 개선

### 2. 의미 기반 메모리 선택

- 현재 질문과 관련 높은 이전 대화만 선택
- 불필요한 컨텍스트 제거
- Embedding similarity 기반

### 3. 멀티턴 대화 평가

- 대화 맥락 이해도 측정
- 참조 해결 정확도 평가
- Ground Truth 데이터셋 구축

## 참고 문서

- [Architecture Overview](./architecture.md)
- [AgenticRAG Implementation](../backend/src/agentic_rag.py)
- [Conversation Memory Module](../backend/src/memory/conversation_memory.py)
