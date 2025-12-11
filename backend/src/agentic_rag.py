from typing import TypedDict, List, Annotated, Optional
from uuid import uuid4
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
    convert_to_messages,
)
from langchain.tools import tool
import time

from src.embeddings.vector_search import VectorSearch
from src.law_api import (
    search_law_list,
    get_law_article,
    get_law_detail,
    format_jo_number,
    extract_article_content
)
from src.config import get_llm
from src.supabase_client import save_conversation
from src.monitoring import get_wandb_logger, AgenticRAGLogger

# ========================================
# Tools 정의
# ========================================

vector_search_instance = VectorSearch()

@tool
def search_vector_db(query: str) -> str:
    """
    벡터 데이터베이스에서 유사한 법령 검색 (첫 번째 단계)

    임베딩된 조문에서 빠르게 검색하고 조문 내용을 바로 반환합니다.
    이 도구를 먼저 호출하여 벡터 DB에 관련 법령이 있는지 확인하세요.

    Args:
        query: 검색할 질문

    Returns:
        - 성공: 법령명, 조문, 유사도, 조문 내용 포함 → 바로 답변 작성!
        - 실패: VECTOR_DB_NO_MATCH → search_law_by_api 사용

    중요: 이 도구가 성공하면 조문 내용이 포함되므로 추가 도구 호출 불필요!
    """
    results = vector_search_instance.search(query, top_k=5, threshold=0.7)

    if not results:
        # 유사도 0.7 이상인 결과가 없음
        return "VECTOR_DB_NO_MATCH: 벡터 DB에서 유사도 0.7 이상인 법령을 찾지 못했습니다. search_law_by_api를 사용하여 직접 검색하세요."

    # 결과를 구조화된 형식으로 반환 (조문 내용 포함)
    result_text = "=== 벡터 검색 결과 (유사도 0.7 이상) ===\n\n"
    for idx, r in enumerate(results[:3], 1):
        result_text += f"[결과 {idx}]\n"
        result_text += f"법령: {r['law_name']}\n"
        result_text += f"조문: {r['article']}\n"
        result_text += f"유사도: {r['similarity']:.2f}\n"
        result_text += f"내용: {r.get('content', '내용 없음')}\n\n"

    result_text += "\n✅ 위 조문 내용으로 답변을 작성하세요. 추가 도구 호출 불필요!"

    return result_text


@tool
def get_full_article_content(law_name: str, article: str, mst: str) -> str:
    """
    법령의 특정 조문 전체 내용 가져오기

    벡터 검색으로 찾은 법령의 전체 내용을 API로 조회

    Args:
        law_name: 법령명
        article: 조문 (예: "제56조")
        mst: 법령일련번호

    Returns:
        조문 전체 내용
    """
    if not mst:
        return "MST(법령일련번호) 정보가 없어 조문을 가져올 수 없습니다. search_law_by_api를 사용하세요."

    # 조 단위 청킹이므로 _part suffix 제거 불필요
    jo_formatted = format_jo_number(article)
    law_data = get_law_article(mst=mst, jo=jo_formatted)
    content = extract_article_content(law_data)

    if content and "오류" not in content:
        return f"=== {law_name} {article} ===\n\n{content}"
    else:
        return f"조문 가져오기 실패: {content}"


@tool
def search_law_by_api(law_name: str, article_number: str = None) -> str:
    """
    API로 법령 직접 검색 (벡터 DB에 없을 때만 사용)

    모든 한국 법령을 실시간 검색합니다.
    search_vector_db에서 VECTOR_DB_NO_MATCH가 반환된 경우에만 사용하세요.

    Args:
        law_name: 검색할 법령명 (예: "근로기준법", "민법", "주택임대차보호법")
        article_number: 선택적 조문 번호 (예: "56조", "제56조", "750조")

    Returns:
        법령의 조문 내용
    """
    # 법령 검색
    search_result = search_law_list(law_name)

    if "error" in search_result:
        return f"법령 검색 실패: {search_result['error']}"

    law_list = search_result.get("LawSearch", {}).get("law", [])

    if isinstance(law_list, dict):
        law_list = [law_list]

    if not law_list:
        return f"'{law_name}' 관련 법령을 찾을 수 없습니다. 법령명을 정확하게 입력해주세요."

    # 가장 관련성 높은 법령 찾기 (이름이 가장 짧은 것 = 기본법)
    law_list.sort(key=lambda x: len(x.get("법령명한글", "")))
    law = law_list[0]
    law_title = law.get("법령명한글")
    mst = law.get("법령일련번호")

    if not mst:
        return "법령일련번호를 찾을 수 없습니다."

    # 특정 조문 검색인지 전체 검색인지 판단
    if article_number:
        # 특정 조문만 가져오기
        jo_formatted = format_jo_number(article_number)
        law_data = get_law_article(mst=mst, jo=jo_formatted)
        content = extract_article_content(law_data)

        if content and "오류" not in content:
            return f"=== {law_title} {article_number} ===\n\n{content}"
        else:
            return f"조문 가져오기 실패: {content}"
    else:
        # 전체 본문 가져오기 (처음 2000자)
        law_data = get_law_detail(mst)
        content = extract_article_content(law_data)

        if content and "오류" not in content:
            return f"=== {law_title} ===\n\n{content[:2000]}\n\n... (이하 생략)"
        else:
            return f"법령 내용 가져오기 실패: {content}"


# ========================================
# State 정의
# ========================================

class AgentState(TypedDict):
    messages: Annotated[List, "messages"]
    question: str
    tool_calls: int  # 방어용: 무한 반복 방지

# ========================================
# Agent 정의
# ========================================

class AgenticRAG:
    def __init__(self):
        # Tool calling용 LLM (정확한 판단 필요)
        self.llm_tools = get_llm("tool_calling")
        # 답변 생성용 LLM (빠른 생성)
        self.llm_generation = get_llm("generation")

        # ⭐ Tools 바인딩 ⭐
        self.tools = [
            search_vector_db,
            get_full_article_content,
            search_law_by_api
        ]
        # Tool calling은 Thinking 모델 사용
        self.llm_with_tools = self.llm_tools.bind_tools(self.tools)
        self.graph = self._build_graph()

        # WandB 로거 초기화
        try:
            self.wandb_logger = AgenticRAGLogger(get_wandb_logger())
        except Exception:
            self.wandb_logger = None

        # 도구 실행 시간 추적
        self.tool_execution_times = {}
    
    def _build_graph(self):
        """LangGraph 구성"""
        workflow = StateGraph(AgentState)

        # 노드
        workflow.add_node("agent", self.call_agent)
        workflow.add_node("tools", self.execute_tools)

        # 플로우
        workflow.set_entry_point("agent")

        workflow.add_conditional_edges(
            "agent",
            self.should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )

        workflow.add_edge("tools", "agent")

        return workflow.compile()

    def execute_tools(self, state: AgentState) -> AgentState:
        """도구 실행 (ToolNode 대체)"""
        messages = state['messages']
        last_message = messages[-1]

        # 도구 호출 실행
        tool_messages = []
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                tool_name = tool_call['name']
                tool_args = tool_call['args']
                tool_id = tool_call['id']

                # 도구 실행
                for tool in self.tools:
                    if tool.name == tool_name:
                        start_time = time.time()
                        success = True
                        result_str = ""

                        try:
                            result = tool.invoke(tool_args)
                            result_str = str(result)
                            tool_messages.append(
                                ToolMessage(
                                    content=result_str,
                                    tool_call_id=tool_id
                                )
                            )
                        except Exception as e:
                            success = False
                            result_str = f"도구 실행 오류: {str(e)}"
                            tool_messages.append(
                                ToolMessage(
                                    content=result_str,
                                    tool_call_id=tool_id
                                )
                            )

                        execution_time = time.time() - start_time

                        # WandB 로깅
                        if self.wandb_logger:
                            self.wandb_logger.log_tool_call(
                                tool_name=tool_name,
                                args=tool_args,
                                result_preview=result_str[:200],
                                execution_time=execution_time,
                                success=success
                            )

                        break

        return {
            "messages": messages + tool_messages,
            "question": state.get("question", ""),
            "tool_calls": state.get("tool_calls", 0),
        }
    
    # ========================================
    # 노드 구현
    # ========================================
    
    def call_agent(self, state: AgentState) -> AgentState:
        """Agent 호출"""
        # LangGraph 상태가 dict/list 등으로 변할 수 있어 확실히 BaseMessage로 변환
        messages = convert_to_messages(state['messages'])

        # 방어적으로 사람이 쓴 메시지가 없으면 에러 방지
        has_human = any(
            isinstance(m, HumanMessage) or getattr(m, "type", "") == "human"
            for m in messages
        )
        if not has_human:
            messages.append(HumanMessage(content=state.get("question", "")))

        # LLM이 도구 선택!
        response = self.llm_with_tools.invoke(messages)

        tool_calls_count = state.get("tool_calls", 0)
        if getattr(response, "tool_calls", None):
            # 도구 호출 개수만큼 카운트 증가
            num_calls = len(response.tool_calls)
            tool_calls_count += num_calls
            # 어떤 도구가 호출되는지 로깅
            for tc in response.tool_calls:
                print(f"🔧 도구 호출: {tc['name']}({', '.join(f'{k}={v}' for k, v in tc['args'].items())})")

        # 메시지 추가
        return {
            "messages": messages + [response],
            "question": state.get("question", ""),
            "tool_calls": tool_calls_count,
        }
    
    def should_continue(self, state: AgentState) -> str:
        """도구 실행 필요?"""
        messages = state['messages']
        last_message = messages[-1]

        # 무한 루프 방지: 최대 10회 (벡터검색 → 조문조회 → API검색 → 재시도)
        if state.get("tool_calls", 0) >= 10:
            print("⚠️ 최대 도구 호출 횟수 도달, 종료합니다.")
            return "end"

        # ⭐ Function Calling 확인 ⭐
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "continue"

        return "end"
    
    # ========================================
    # 실행
    # ========================================
    
    def run(self, question: str, session_id: Optional[str] = None) -> str:
        """Agent 실행 (non-streaming, backward compatibility)"""
        # 스트리밍을 내부적으로 실행하고 전체 결과만 반환
        full_answer = ""
        for chunk in self.run_stream(question, session_id):
            full_answer += chunk
        return full_answer

    def run_stream(self, question: str, session_id: Optional[str] = None):
        """Agent 실행 (streaming)"""
        start_time = time.time()
        print(f"\n{'='*60}")
        print(f"🤖 Agentic RAG 시작 (스트리밍)")
        print(f"❓ 질문: {question}")
        print(f"{'='*60}\n")

        # 세션 아이디 없으면 새로 발급 (대화 기록용)
        session_id = session_id or str(uuid4())
        # 이전 검색 결과 초기화 (로그 저장용)
        vector_search_instance.last_results = []

        # WandB 세션 시작
        if self.wandb_logger:
            self.wandb_logger.start_session(question)

        # 초기 메시지
        initial_messages = [
            SystemMessage(
                content="""한국 법률 상담 AI입니다. 반드시 아래 단계를 따라 작업하세요:

1단계: search_vector_db(질문)로 벡터 DB 검색

2단계:
  A. 벡터 검색 성공 시 (유사도 0.7 이상):
     → 검색 결과에 "내용" 필드가 포함되어 있습니다
     → 즉시 해당 내용으로 답변 작성 (추가 도구 호출 금지!)
     → get_full_article_content 호출하지 마세요!

  B. 벡터 검색 실패 시 (VECTOR_DB_NO_MATCH):
     → search_law_by_api(법령명)로 API 검색
     → 예: "택배 분실" → search_law_by_api("전자상거래법")

3단계: 조회한 법령 내용으로 답변 작성

답변 형식:
- 요약
- 근거 법령 (법령명 + 조문)
- 조문 내용

중요 규칙:
1. 벡터 검색 결과에 "내용"이 있으면 바로 답변 작성! (API 호출 금지)
2. get_full_article_content는 특별한 경우에만 사용 (벡터 검색에서 내용이 없을 때)
3. 동일한 도구를 반복 호출하지 마세요"""
            ),
            HumanMessage(content=question)
        ]

        initial_state = {
            "messages": initial_messages,
            "question": question,
            "tool_calls": 0,
        }

        full_answer = ""

        try:
            # 1단계: Tool calling 완료까지 실행 (non-streaming)
            graph_start = time.time()
            print("⏱️  그래프 실행 시작...")

            final_state = None
            for event in self.graph.stream(initial_state):
                final_state = event

            graph_time = time.time() - graph_start
            print(f"⏱️  그래프 실행 완료: {graph_time:.2f}초")

            # 마지막 상태에서 메시지 추출
            if not final_state:
                yield "오류: 응답을 생성할 수 없습니다."
                return

            # 가장 마지막 노드의 출력 가져오기
            last_node_output = list(final_state.values())[-1]
            messages = last_node_output.get("messages", [])

            # 마지막 메시지가 AI의 답변이면 그것을 스트리밍
            last_msg = messages[-1]
            if hasattr(last_msg, 'content') and isinstance(last_msg.content, str):
                # 이미 생성된 답변을 청크로 나누어 스트리밍 (지연 없이)
                answer_text = last_msg.content
                print(f"📝 답변 생성 완료 ({len(answer_text)}자), 스트리밍 중...")

                # 10자씩 묶어서 스트리밍 (프론트엔드에서 타이핑 효과 처리)
                chunk_size = 10
                for i in range(0, len(answer_text), chunk_size):
                    chunk_text = answer_text[i:i+chunk_size]
                    full_answer += chunk_text
                    yield chunk_text
            else:
                # 2단계: 최종 답변 생성 (LLM 스트리밍) - 답변이 아직 없는 경우
                # Tool calling 결과를 바탕으로 답변 생성용 LLM에게 전달
                print("📝 답변 생성 중 (스트리밍)...")

                for chunk in self.llm_generation.stream(messages):
                    # Gemini의 응답 형식 처리
                    chunk_text = ""

                    if hasattr(chunk, 'content'):
                        content = chunk.content

                        # 빈 content 체크
                        if not content:
                            continue

                        # 리스트 형식 처리
                        if isinstance(content, list):
                            for part in content:
                                if isinstance(part, dict) and 'text' in part:
                                    chunk_text += part['text']
                        # 문자열 형식 처리
                        elif isinstance(content, str):
                            chunk_text = content
                        else:
                            chunk_text = str(content)

                        # 디버깅 로그
                        if chunk_text:
                            print(f"📤 Chunk ({len(chunk_text)}자): {chunk_text[:50]}...")
                            full_answer += chunk_text
                            yield chunk_text

        except Exception as e:
            error_msg = f"\n\n❌ 오류 발생: {str(e)}\n"
            yield error_msg
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
