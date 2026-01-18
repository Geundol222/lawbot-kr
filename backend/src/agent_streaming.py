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

    def __init__(self, graph, llm, wandb_logger=None, memory=None):
        """
        Args:
            graph: 컴파일된 LangGraph
            llm: 답변 생성용 LLM
            wandb_logger: WandB 로거 (선택)
            memory: ConversationMemory (선택)
        """
        self.graph = graph
        self.llm = llm
        self.wandb_logger = wandb_logger
        self.memory = memory

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
- 충분한 정보를 얻으면 종료하세요

**이전 대화가 있다면 맥락을 고려하여 검색하세요.**"""
            )
        ]

        # 이전 대화 이력 추가 (메모리가 있으면)
        if self.memory:
            previous_messages = self.memory.get_messages()
            initial_messages.extend(previous_messages)

        # 현재 질문 추가
        initial_messages.append(HumanMessage(content=question))

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

            # 답변 생성용 메시지 필터링
            # - 현재 질문(Human)과 검색 결과(Tool)만 사용
            # - 이전 대화 맥락은 SystemMessage로 전달 (출력되지 않도록)
            filtered_messages = []
            context_system_msg = None

            # 이전 대화 맥락 요약 (메모리에서) - SystemMessage로 전달
            if self.memory and self.memory.get_messages():
                context_summary = []
                memory_msgs = self.memory.get_messages()
                for msg in memory_msgs[-4:]:  # 최근 2턴만
                    msg_type = getattr(msg, "type", "")
                    content = str(getattr(msg, "content", ""))[:200]  # 200자로 제한
                    if msg_type == "human":
                        context_summary.append(f"사용자: {content}")
                    elif msg_type == "ai":
                        context_summary.append(f"AI: {content}")

                if context_summary:
                    # SystemMessage로 전달하여 출력되지 않도록 함
                    context_system_msg = SystemMessage(
                        content=f"[참고: 이전 대화 맥락 - 이 내용을 출력하지 말고 맥락 이해에만 사용하세요]\n" + "\n".join(context_summary)
                    )

            # 현재 세션의 메시지에서 Human과 Tool만 추출
            memory_message_count = len(self.memory.get_messages()) if self.memory else 0
            for idx, msg in enumerate(messages):
                if idx < memory_message_count:
                    continue  # 메모리 메시지는 위에서 요약으로 처리

                msg_type = getattr(msg, "type", "")
                if msg_type == "human":
                    filtered_messages.append(msg)
                elif msg_type == "tool":
                    # Tool 결과만 추가 (검색 결과)
                    filtered_messages.append(msg)

            # 답변 생성용 프롬프트 추가
            answer_generation_prompt = SystemMessage(
                content="""당신은 전문적인 법률 상담 AI입니다. 검색된 법령 정보를 바탕으로 상세하게 답변하세요.

**[출력 형식]**
## 신뢰도
(0.0~1.0)

## 답변
(본문)

**[작성 규칙]**
1. 바로 본론으로 시작 (사과, 인사, 불필요한 서두 금지)
2. 법령 인용: "~~법 제X조에 따르면" 형식
3. 구체적 수치/기준/예시를 충분히 포함
4. 관련 조항이 여러 개면 모두 설명
5. 실질적 조언 포함 (신청 방법, 필요 서류, 기한 등)

**[질문 유형별 톤]**
- 정보성 질문 ("~이 뭔가요?", "~어떻게 되나요?"): 객관적으로 상세히 설명
- 상담성 질문 ("~당했는데", "~어떡하죠?"): 공감 표현 후 조언

**[이전 대화 맥락]**
- [이전 대화 맥락] 태그가 있으면 연계 질문으로 이해
- 이미 설명한 내용은 간략히, 새로운 정보는 상세히

**[금지사항]**
- "죄송합니다", "이전 대화를 잘못 이해했습니다" 등 사과 금지
- search_vector_db() 같은 함수 출력 금지
- 마크다운 헤더(###, ####) 금지

**[예시 1: 정보성 질문]**
질문: "연장근로 가산임금이 어떻게 되나요?"
## 신뢰도
0.95

## 답변
근로기준법 제56조에 따르면 연장근로에 대해 통상임금의 50% 이상을 가산해야 합니다. 즉, 시급 10,000원인 근로자가 1시간 연장근로 시 15,000원(10,000원 + 5,000원 가산)을 받아야 합니다. 야간근로(22시~06시)는 별도로 50% 가산되며, 휴일근로는 8시간 이내 50%, 8시간 초과분은 100% 가산됩니다. 연장근로와 야간근로가 겹치면 각각 가산되어 통상임금의 100%가 추가됩니다.

**[예시 2: 상담성 질문]**
질문: "부당해고 당했는데 어떻게 해야 하나요?"
## 신뢰도
0.95

## 답변
부당해고로 힘드시겠어요. 근로기준법 제28조에 따르면 해고일로부터 3개월 이내 노동위원회에 구제신청이 가능합니다. 신청서(별지 제3호 서식)와 해고통지서, 근로계약서, 급여명세서 등을 준비하세요. 노동위원회는 심문 후 부당해고로 판정되면 원직복직 또는 금전보상 명령을 내립니다. 회사가 불이행 시 이행강제금이 부과되며, 형사처벌도 가능합니다.

**[예시 3: 연계 질문]**
(이전: 부당해고 대처법 → 현재: "5인 미만 사업장인데도?")
## 신뢰도
0.90

## 답변
5인 미만 사업장이시군요. 안타깝게도 근로기준법 제11조에 따르면 상시 5인 미만 사업장에는 부당해고 구제신청 규정(제28조)이 적용되지 않습니다. 다만 대안이 있습니다. 민사소송으로 해고무효 확인을 받거나, 임금체불·퇴직금 미지급 등 다른 위반사항이 있다면 고용노동부에 진정을 제기할 수 있습니다. 또한 해고 사유가 차별(성별, 나이 등)에 해당하면 국가인권위원회에 진정도 가능합니다."""
            )

            # 답변 생성 메시지 구성 (이전 맥락이 있으면 SystemMessage로 추가)
            answer_messages = []
            if context_system_msg:
                answer_messages.append(context_system_msg)
            answer_messages.extend(filtered_messages)
            answer_messages.append(answer_generation_prompt)

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

        # 대화 저장 (Supabase + Memory)
        try:
            law_name = None
            article = None
            if vector_search_instance.last_results:
                top = vector_search_instance.last_results[0]
                law_name = top.get("law_name")
                article = top.get("article")

            response_time_ms = int((time.time() - start_time) * 1000)

            # 메모리에 저장 (SupabaseConversationMemory면 DB도 자동 저장)
            if self.memory and hasattr(self.memory, 'add_and_save'):
                self.memory.add_and_save(
                    user_question=question,
                    bot_answer=full_answer,
                    law_name=law_name,
                    article=article,
                    response_time_ms=response_time_ms
                )
            elif self.memory:
                # 기본 ConversationMemory인 경우
                self.memory.add_user_message(question)
                self.memory.add_ai_message(full_answer)
                # DB 저장은 별도로
                save_conversation(
                    session_id=session_id,
                    user_question=question,
                    bot_answer=full_answer,
                    law_name=law_name,
                    article=article,
                    response_time_ms=response_time_ms
                )
            else:
                # 메모리 없으면 DB만 저장
                save_conversation(
                    session_id=session_id,
                    user_question=question,
                    bot_answer=full_answer,
                    law_name=law_name,
                    article=article,
                    response_time_ms=response_time_ms
                )
        except Exception as e:
            print(f"⚠️ 대화 저장 실패: {e}")

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
