from typing import TypedDict, List, Annotated
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

from src.embeddings.vector_search import VectorSearch
from src.law_api import (
    search_law_list,
    get_law_article,
    get_law_detail,
    format_jo_number,
    extract_article_content
)
from src.config import get_llm

# ========================================
# Tools 정의
# ========================================

vector_search_instance = VectorSearch()

@tool
def search_vector_db(query: str) -> str:
    """
    벡터 데이터베이스에서 유사한 법령 검색 (첫 번째 단계)

    임베딩된 3,926개 조문에서 빠르게 검색
    이 도구를 먼저 호출하여 벡터 DB에 관련 법령이 있는지 확인해야 합니다.

    Args:
        query: 검색할 질문

    Returns:
        유사한 법령 목록 (법령명, 조문, MST, 유사도)
        - 유사도 0.7 이상: 조문 정보 반환 → get_full_article_content 사용
        - 유사도 0.7 미만: VECTOR_DB_NO_MATCH → search_law_by_api 사용
    """
    results = vector_search_instance.search(query, top_k=5, threshold=0.7)

    if not results:
        # 유사도 0.7 이상인 결과가 없음
        return "VECTOR_DB_NO_MATCH: 벡터 DB에서 유사도 0.7 이상인 법령을 찾지 못했습니다. search_law_by_api를 사용하여 직접 검색하세요."

    # 결과를 구조화된 형식으로 반환
    result_text = "=== 벡터 검색 결과 (유사도 0.7 이상) ===\n\n"
    for idx, r in enumerate(results[:3], 1):
        result_text += f"[결과 {idx}]\n"
        result_text += f"법령: {r['law_name']}\n"
        result_text += f"조문: {r['article']}\n"
        mst_text = r.get('mst') or "없음"
        result_text += f"MST: {mst_text}\n"
        result_text += f"유사도: {r['similarity']:.2f}\n\n"

    result_text += "\n💡 다음 단계: get_full_article_content를 사용하여 조문의 전체 내용을 가져오세요."

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
        self.llm = get_llm()
        
        # ⭐ Tools 바인딩 ⭐
        self.tools = [
            search_vector_db,
            get_full_article_content,
            search_law_by_api
        ]
        # 도구는 프롬프트 지시에 따라 선택
        self.llm_with_tools = self.llm.bind_tools(self.tools)
        self.graph = self._build_graph()
    
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

                # 도구 실행 로그 제거 (너무 장황함)

                # 도구 실행
                for tool in self.tools:
                    if tool.name == tool_name:
                        try:
                            result = tool.invoke(tool_args)
                            tool_messages.append(
                                ToolMessage(
                                    content=str(result),
                                    tool_call_id=tool_id
                                )
                            )
                        except Exception as e:
                            tool_messages.append(
                                ToolMessage(
                                    content=f"도구 실행 오류: {str(e)}",
                                    tool_call_id=tool_id
                                )
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

        # 무한 루프 방지: 최대 3회 (벡터검색 → 조문조회 또는 API검색)
        if state.get("tool_calls", 0) >= 3:
            print("⚠️ 최대 도구 호출 횟수 도달, 종료합니다.")
            return "end"

        # ⭐ Function Calling 확인 ⭐
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "continue"

        return "end"
    
    # ========================================
    # 실행
    # ========================================
    
    def run(self, question: str) -> str:
        """Agent 실행"""
        print(f"\n{'='*60}")
        print(f"🤖 Agentic RAG 시작")
        print(f"❓ 질문: {question}")
        print(f"{'='*60}\n")

        # 초기 메시지
        initial_messages = [
            SystemMessage(
                content="""한국 법률 상담 AI입니다. 아래 단계를 따라 작업하세요:

1단계: search_vector_db(질문)로 벡터 DB 검색
2단계:
  - 벡터 검색 결과가 있으면 → get_full_article_content(법령명, 조문, MST)로 전체 조문 조회
  - VECTOR_DB_NO_MATCH가 나오면 → search_law_by_api(법령명, 조문번호)로 API 검색
3단계: 조회한 법령 내용으로 답변 작성

답변 형식:
- 요약
- 근거 법령
- 조문 내용

중요: 동일한 도구를 반복 호출하지 마세요."""
            ),
            HumanMessage(content=question)
        ]

        initial_state = {
            "messages": initial_messages,
            "question": question,
            "tool_calls": 0,
        }

        # LangGraph 실행
        result = self.graph.invoke(initial_state)

        print(f"\n{'='*60}")
        print(f"✅ 완료!")
        print(f"{'='*60}\n")

        # 마지막 AI 메시지 반환
        final_message = result['messages'][-1]

        if hasattr(final_message, 'content'):
            content = final_message.content
            # content가 리스트인 경우 (Gemini 응답 형식)
            if isinstance(content, list):
                text_parts = [part.get('text', '') for part in content if isinstance(part, dict) and 'text' in part]
                return '\n'.join(text_parts)
            return str(content)
        else:
            return str(final_message)
