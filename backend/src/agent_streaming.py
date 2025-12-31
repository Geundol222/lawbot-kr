"""
Agent 스트리밍 로직
- run_stream: 스트리밍 응답 생성
"""

import time
import asyncio
from uuid import uuid4
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage

from src.embeddings.vector_search import VectorSearch
from src.supabase_client import save_conversation
from src.config import llm_stream_with_retry


vector_search_instance = VectorSearch()


class AgentStreaming:
    """Agent 스트리밍 로직을 담당하는 클래스"""

    def __init__(self, graph, llm, wandb_logger=None):
        """
        Args:
            graph: 컴파일된 LangGraph
            llm: 답변 생성용 LLM
            wandb_logger: WandB 로거 (선택)
        """
        self.graph = graph
        self.llm = llm
        self.wandb_logger = wandb_logger

    def _run_stream_sync(self, question: str, session_id: str, start_time: float):
        """동기 스트리밍 로직 - SSE 이벤트 전송"""
        import json
        full_answer = ""
        law_content = ""  # 검색된 법령 내용 저장

        # 초기 메시지 - 그래프용 (도구 호출만)
        initial_messages = [
            SystemMessage(
                content="""당신은 한국 법령 정보 수집 에이전트입니다. 도구만 호출하세요.

**필수 플로우:**
1. search_vector_db(사용자 질문) - 벡터 DB에서 먼저 검색
2. 벡터 검색 성공 시:
   - check_exceptions_needed(법령 내용, 질문)로 예외 조항 필요 여부 판단
   - 예외 조항이 필요하면 해당 조문 추가 검색
   - 추가 검색 대상이 별표/별지/서식이면 search_byeol(법령명, 별표 번호) 호출
   - 수집된 조문에 대해 search_prec_by_article(법령명, 조문)으로 관련 판례 요지 조회
3. 벡터 검색 실패 시 (VECTOR_DB_NO_MATCH):
   - search_law_by_api(법령명, 질문)로 직접 검색
   - check_exceptions_needed(법령 내용, 질문)로 예외 조항 확인
   - 수집된 조문이 있으면 search_prec_by_article로 판례 요지 조회

**중요 규칙:**
- 도구 호출만 하세요 (텍스트 답변 작성 금지)
- 같은 법령을 중복 검색하지 마세요
- check_exceptions_needed 결과에 따라 추가 조문 검색
- 별표/별지/서식이 발견되면 search_byeol로 별표 본문을 함께 조회
- 충분한 정보를 얻으면 종료하세요"""
            ),
            HumanMessage(content=question)
        ]

        initial_state = {
            "messages": initial_messages,
            "question": question,
            "tool_calls": 0,
            "exceptions_checked": False,
        }

        try:
            # 1단계: Tool calling을 단계별로 실행하며 SSE 이벤트 전송
            graph_start = time.time()
            print("⏱️  그래프 실행 시작...")

            final_state = None
            last_tool_name = None

            for event in self.graph.stream(initial_state):
                final_state = event

                # 현재 노드 확인
                node_name = list(event.keys())[0] if event else None
                node_data = list(event.values())[0] if event else None

                if node_data and 'messages' in node_data:
                    last_msg = node_data['messages'][-1]

                    # Tool 메시지 감지 (Tool 실행 완료)
                    if hasattr(last_msg, '__class__') and last_msg.__class__.__name__ == 'ToolMessage':
                        tool_content = last_msg.content if hasattr(last_msg, 'content') else ""

                        # 법령 검색 완료
                        if last_tool_name in ['search_vector_db', 'search_law_by_api']:
                            law_content = tool_content
                            # SSE 이벤트 전송하지 않음 (프론트에서 자동 표시)

                        # 예외조항 확인 완료
                        elif last_tool_name == 'check_exceptions_needed':
                            try:
                                result = json.loads(tool_content)
                                if result.get('needed'):
                                    # 예외조항 필요 - SSE 이벤트 전송
                                    event_data = json.dumps({
                                        "type": "checking_exceptions",
                                        "articles": result.get('articles_to_search', []),
                                        "reason": result.get('reason', '')
                                    }, ensure_ascii=False)
                                    yield f"data: {event_data}\n\n"
                            except:
                                pass

                    # AI 메시지 감지 (Tool 호출 요청)
                    elif hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                        for tool_call in last_msg.tool_calls:
                            tool_name = tool_call['name']
                            last_tool_name = tool_name

                            # 법령 검색 시작
                            if tool_name in ['search_vector_db', 'search_law_by_api']:
                                event_data = json.dumps({
                                    "type": "searching",
                                    "message": "법령을 검색 중입니다..."
                                }, ensure_ascii=False)
                                yield f"data: {event_data}\n\n"

            graph_time = time.time() - graph_start
            print(f"⏱️  그래프 실행 완료: {graph_time:.2f}초")

            # 마지막 상태에서 메시지 추출
            if not final_state:
                error_event = json.dumps({
                    "type": "error",
                    "message": "응답을 생성할 수 없습니다."
                }, ensure_ascii=False)
                yield f"data: {error_event}\n\n"
                return

            # 가장 마지막 노드의 출력 가져오기
            last_node_output = list(final_state.values())[-1]
            messages = last_node_output.get("messages", [])

            # 진단: 마지막 AI 메시지 확인
            print(f"\n📊 총 메시지 개수: {len(messages)}")
            for i, msg in enumerate(messages[-3:]):  # 마지막 3개만
                msg_type = getattr(msg, 'type', 'unknown')
                has_tool_calls = hasattr(msg, 'tool_calls') and bool(msg.tool_calls)
                content_preview = str(getattr(msg, 'content', ''))[:100]
                print(f"  [{i}] {msg_type} | tool_calls={has_tool_calls} | content={content_preview}")

            # 최종 답변 시작 이벤트
            answer_start_event = json.dumps({
                "type": "answer_start",
                "message": ""
            }, ensure_ascii=False)
            yield f"data: {answer_start_event}\n\n"

            # ========== 답변 생성: 스트리밍 ==========
            # 그래프가 수집한 법령 정보로 실시간 답변 생성
            print(f"📝 법령 정보 수집 완료, 실시간 답변 생성 시작...")

            # 답변 생성에 불필요한 system(도구만 호출) 메시지 제거, human/tool만 유지
            filtered_messages = []
            for msg in messages:
                msg_type = getattr(msg, "type", "")
                if msg_type in ("human", "tool"):
                    filtered_messages.append(msg)
                # ai/system 메시지는 최종 답변 생성 단계에서 제외

            # 답변 생성용 프롬프트 추가
            answer_generation_prompt = SystemMessage(
                content="""위 메시지에서 도구(tool)가 전달한 법령/판례 정보를 바탕으로 답변을 작성하세요.

**중요: 도구 결과 확인 방법**
- 위 메시지 중 "=== 벡터 검색 결과 ===" 섹션에서 법령명, 조문, 내용을 찾으세요
- "=== 관련 판례 요지 ===" 섹션에서 판례 정보를 찾으세요
- 법령명과 조문 번호를 **반드시** "근거 법령" 섹션에 나열하세요

**답변 작성 지침:**
1. 도구 결과의 "법령:" 부분에서 법령명 추출 → "근거 법령" 섹션에 작성
2. 도구 결과의 "조문:" 부분에서 조문 번호 추출 → "근거 법령" 섹션에 작성
3. 도구 결과의 "내용:" 부분을 "법령 내용" 섹션에 원문 그대로 복사
4. 판례 요지가 있으면 "관련 판례 요지" 섹션에 작성
5. 5인 미만 적용처럼 논쟁이 있으면 양측 근거 병기

**반드시 아래 형식을 따르세요 (섹션 누락 금지):**

## 신뢰도
[0.0 ~ 1.0 점수]
- 1.0: 질문에 정확히 답하는 법령/판례 발견
- 0.5 ~ 0.9: 관련 법령/판례는 있으나 직접적 답변 아님
- 0.0 ~ 0.4: 관련 자료 부족

## 결론
[명확한 답변, 논쟁 시 양측 근거 병기]

## 근거 법령
- 법령명 조문 (예: 근로기준법 제56조)
- 법령명 조문 (예: 근로기준법 시행령 제10조)

## 관련 판례 요지
- [있을 때만] 판례명/사건번호/요지/참조조문

## 법령 내용
**법령명 조문**
[도구 결과의 "내용:" 부분을 원문 그대로]

## 구체적 설명
[상세 설명]"""
            )

            # 답변 생성 메시지 구성
            answer_messages = filtered_messages + [answer_generation_prompt]

            # 디버깅: 답변 생성에 사용되는 메시지 확인
            print(f"\n🔍 [DEBUG] 답변 생성용 메시지 개수: {len(answer_messages)}")
            for i, msg in enumerate(answer_messages[-5:]):  # 마지막 5개만
                msg_type = getattr(msg, 'type', 'unknown')
                content_preview = str(getattr(msg, 'content', ''))[:150]
                print(f"  [{i}] {msg_type}: {content_preview}...")

            # 실시간 스트리밍 (재시도 로직 포함)
            print(f"\n🔍 [DEBUG] LLM 스트리밍 시작...")
            chunk_count = 0
            for chunk in llm_stream_with_retry(self.llm, answer_messages):
                chunk_count += 1
                if chunk_count <= 3:  # 처음 3개 청크만 로깅
                    print(f"  [청크 {chunk_count}] {chunk}")
                chunk_text = ""
                if hasattr(chunk, 'content'):
                    content = chunk.content
                    if not content:
                        continue

                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and 'text' in part:
                                chunk_text += part['text']
                    elif isinstance(content, str):
                        chunk_text = content
                    else:
                        chunk_text = str(content)

                    if chunk_text:
                        full_answer += chunk_text
                        chunk_event = json.dumps({
                            "type": "answer_chunk",
                            "text": chunk_text
                        }, ensure_ascii=False)
                        yield f"data: {chunk_event}\n\n"

            # 스트리밍이 비어 있으면 마지막 메시지의 content를 그대로 반환 (테스트/모킹 대비)
            if chunk_count == 0 and not full_answer:
                last_with_content = next((m for m in reversed(messages) if hasattr(m, "content")), None)
                fallback_text = str(getattr(last_with_content, "content", "") or "")
                if fallback_text:
                    full_answer += fallback_text
                    chunk_event = json.dumps({
                        "type": "answer_chunk",
                        "text": fallback_text
                    }, ensure_ascii=False)
                    yield f"data: {chunk_event}\n\n"

            print(f"\n🔍 [DEBUG] 총 {chunk_count}개 청크 수신")
            print(f"📝 답변 스트리밍 완료: {len(full_answer)}자")

            # 답변 완료 이벤트 - 법령 출처 포함
            law_references = []
            if vector_search_instance.last_results:
                # 검색 결과에서 법령 출처 수집 (중복 제거)
                seen = set()
                for result in vector_search_instance.last_results[:5]:  # 상위 5개만
                    law_name = result.get("law_name")
                    article = result.get("article")
                    if law_name and article:
                        key = f"{law_name}:{article}"
                        if key not in seen:
                            law_references.append({
                                "law_name": law_name,
                                "article": article
                            })
                            seen.add(key)

            if law_references:
                complete_event = json.dumps({
                    "type": "answer_complete",
                    "law_references": law_references
                }, ensure_ascii=False)
                yield f"data: {complete_event}\n\n"

        except Exception as e:
            import traceback
            error_msg = f"❌ 오류 발생: {str(e)}"
            print(f"❌ 오류: {e}")
            print(f"❌ 상세 traceback:")
            traceback.print_exc()

            error_event = json.dumps({
                "type": "error",
                "message": error_msg
            }, ensure_ascii=False)
            yield f"data: {error_event}\n\n"
            full_answer += error_msg

        print(f"\n{'='*60}")
        print(f"✅ 완료! (총 {len(full_answer)}자)")
        print(f"{'='*60}\n")

        # WandB 세션 종료 및 로깅
        if self.wandb_logger:
            total_tokens = len(question.split()) + len(full_answer.split())
            self.wandb_logger.end_session(full_answer, total_tokens)

        # Supabase 대화 로그 저장
        try:
            law_name = None
            article = None
            if vector_search_instance.last_results:
                top = vector_search_instance.last_results[0]
                law_name = top.get("law_name")
                article = top.get("article")

            save_conversation(
                session_id=session_id,
                user_question=question,
                bot_answer=full_answer,
                law_name=law_name,
                article=article,
                response_time_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            print(f"⚠️ Supabase 대화 저장 실패: {e}")

    def run_stream(self, question: str, session_id: Optional[str] = None):
        """Agent 실행 (streaming)"""
        start_time = time.time()
        print(f"\n{'='*60}")
        print(f"🤖 Agentic RAG 시작 (실시간 스트리밍)")
        print(f"❓ 질문: {question}")
        print(f"{'='*60}\n")

        # 세션 아이디 없으면 새로 발급 (대화 기록용)
        session_id = session_id or str(uuid4())
        # 이전 검색 결과 초기화 (로그 저장용)
        vector_search_instance.last_results = []

        # WandB 세션 시작
        if self.wandb_logger:
            self.wandb_logger.start_session(question)

        # 동기 스트리밍 실행
        for chunk in self._run_stream_sync(question, session_id, start_time):
            yield chunk
