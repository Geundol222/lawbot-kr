"""
Agentic RAG 시스템
- 도구 정의
- 그래프 구성
- 실행 인터페이스
"""

from typing import Optional
from langgraph.graph import StateGraph, END
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
from src.monitoring import get_wandb_logger, AgenticRAGLogger
from src.agent_state import AgentState
from src.agent_nodes import AgentNodes
from src.agent_streaming import AgentStreaming


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
# Agent 정의
# ========================================

class AgenticRAG:
    def __init__(self, session_id: Optional[str] = None):
        """
        AgenticRAG 초기화

        Args:
            session_id: 세션 ID (프론트엔드에서 전달, WandB 로깅용)
        """
        self.session_id = session_id

        # 단일 LLM 사용 (Gemini 2.5 Flash)
        self.llm = get_llm("flash")

        # ⭐ Tools 바인딩 ⭐
        self.tools = [
            search_vector_db,
            get_full_article_content,
            search_law_by_api
        ]
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        # WandB 로거 초기화 (세션별)
        try:
            self.wandb_logger = AgenticRAGLogger(get_wandb_logger(session_id))
        except Exception as e:
            print(f"⚠️ WandB 로거 초기화 실패: {e}")
            self.wandb_logger = None

        # 노드 로직
        self.nodes = AgentNodes(
            llm_with_tools=self.llm_with_tools,
            tools=self.tools,
            wandb_logger=self.wandb_logger
        )

        # 그래프 빌드
        self.graph = self._build_graph()

        # 스트리밍 로직
        self.streaming = AgentStreaming(
            graph=self.graph,
            llm=self.llm,
            wandb_logger=self.wandb_logger
        )

    def _build_graph(self):
        """LangGraph 구성"""
        workflow = StateGraph(AgentState)

        # 노드
        workflow.add_node("agent", self.nodes.call_agent)
        workflow.add_node("tools", self.nodes.execute_tools)

        # 플로우
        workflow.set_entry_point("agent")

        workflow.add_conditional_edges(
            "agent",
            self.nodes.should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )

        workflow.add_edge("tools", "agent")

        return workflow.compile()

    # ========================================
    # 실행 인터페이스
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
        return self.streaming.run_stream(question, session_id)
