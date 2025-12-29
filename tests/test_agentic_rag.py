"""
AgenticRAG 통합 테스트
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from backend.src.agentic_rag import AgenticRAG


@pytest.mark.integration
class TestAgenticRAGIntegration:
    """AgenticRAG 전체 흐름 테스트"""

    @patch("backend.src.agentic_rag.vector_search_instance")
    @patch("backend.src.agentic_rag.get_llm")
    def test_run_with_vector_search_success(self, mock_get_llm, mock_vector_search, sample_vector_search_results):
        """벡터 검색 성공 시 전체 흐름"""
        # 벡터 검색 Mock
        mock_vector_search.search.return_value = sample_vector_search_results

        # LLM Mock
        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()

        # 도구 호출 응답 (벡터 검색 도구)
        tool_call_response = MagicMock()
        tool_call_response.content = []
        tool_call_response.tool_calls = [
            {
                "name": "search_vector_db",
                "args": {"query": "야근수당"},
                "id": "call_1"
            }
        ]
        tool_call_response.additional_kwargs = {}

        # 최종 답변 응답
        final_response = MagicMock()
        final_response.content = "야근수당은 통상임금의 50% 이상을 가산하여 지급해야 합니다."
        final_response.tool_calls = []
        final_response.additional_kwargs = {}

        mock_llm_with_tools.invoke.side_effect = [tool_call_response, final_response]
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_get_llm.return_value = mock_llm

        # 테스트 실행
        agent = AgenticRAG()
        result = agent.run("야근수당은 얼마나 받을 수 있어?")

        assert result
        assert isinstance(result, str)

    @patch("backend.src.agentic_rag.search_law_list")
    @patch("backend.src.agentic_rag.vector_search_instance")
    @patch("backend.src.agentic_rag.get_llm")
    def test_run_with_api_fallback(self, mock_get_llm, mock_vector_search, mock_search_law):
        """벡터 검색 실패 → API 검색 폴백"""
        # 벡터 검색 실패 (유사도 낮음)
        mock_vector_search.search.return_value = []

        # API 검색 성공
        mock_search_law.return_value = {
            "LawSearch": {
                "law": {
                    "법령명한글": "근로기준법",
                    "법령일련번호": "001234"
                }
            }
        }

        # LLM Mock
        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()

        # 1. 벡터 검색 시도
        vector_search_response = MagicMock()
        vector_search_response.content = []
        vector_search_response.tool_calls = [
            {
                "name": "search_vector_db",
                "args": {"query": "택배 분실"},
                "id": "call_1"
            }
        ]

        # 2. API 검색 시도
        api_search_response = MagicMock()
        api_search_response.content = []
        api_search_response.tool_calls = [
            {
                "name": "search_law_by_api",
                "args": {"law_name": "전자상거래법"},
                "id": "call_2"
            }
        ]

        # 3. 최종 답변
        final_response = MagicMock()
        final_response.content = "전자상거래법에 따라 소비자는 배송 중 분실된 물품에 대해 보호받을 수 있습니다."
        final_response.tool_calls = []

        mock_llm_with_tools.invoke.side_effect = [
            vector_search_response,
            api_search_response,
            final_response
        ]
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_get_llm.return_value = mock_llm

        # 테스트 실행
        with patch("backend.src.agentic_rag.extract_article_content", return_value="전자상거래법 조문 내용"):
            agent = AgenticRAG()
            result = agent.run("택배가 분실되었을 때 소비자 보호는?")

        assert result
        assert isinstance(result, str)

    @patch("backend.src.agentic_rag.get_llm")
    def test_run_stream(self, mock_get_llm):
        """스트리밍 실행 테스트"""
        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()

        # 도구 호출 없이 바로 답변
        final_response = MagicMock()
        final_response.content = "테스트 답변입니다."
        final_response.tool_calls = []

        mock_llm_with_tools.invoke.return_value = final_response
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_get_llm.return_value = mock_llm

        agent = AgenticRAG()

        # 스트리밍 실행
        chunks = list(agent.run_stream("테스트 질문"))

        assert len(chunks) > 0
        full_answer = "".join(chunks)
        assert "테스트 답변" in full_answer

    @patch("backend.src.agentic_rag.get_llm")
    def test_max_tool_calls_limit(self, mock_get_llm):
        """도구 호출 횟수 제한 테스트 (10회)"""
        mock_llm = MagicMock()
        mock_llm_with_tools = MagicMock()

        # 계속 도구 호출만 하도록 설정
        tool_call_response = MagicMock()
        tool_call_response.content = []
        tool_call_response.tool_calls = [
            {
                "name": "search_vector_db",
                "args": {"query": "테스트"},
                "id": f"call_1"
            }
        ]

        # 11번째 호출에서는 답변 생성
        final_response = MagicMock()
        final_response.content = "최대 호출 횟수 도달"
        final_response.tool_calls = []

        mock_llm_with_tools.invoke.side_effect = (
            [tool_call_response] * 10 + [final_response]
        )
        mock_llm.bind_tools.return_value = mock_llm_with_tools
        mock_get_llm.return_value = mock_llm

        with patch("backend.src.agentic_rag.vector_search_instance") as mock_vs:
            mock_vs.search.return_value = []

            agent = AgenticRAG()
            result = agent.run("테스트")

            # 10회 제한에 걸려야 함
            assert result


@pytest.mark.unit
class TestAgenticRAGUnit:
    """AgenticRAG 단위 기능 테스트"""

    @patch("backend.src.agentic_rag.get_llm")
    def test_initialization(self, mock_get_llm):
        """초기화 테스트"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        agent = AgenticRAG()

        assert agent.llm is not None
        assert agent.tools is not None
        # search_vector_db, get_full_article_content, search_byeol, search_law_by_api, search_prec_by_article
        assert len(agent.tools) == 5
        assert agent.graph is not None

    @patch("backend.src.agentic_rag.get_llm")
    def test_graph_structure(self, mock_get_llm):
        """그래프 구조 검증"""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        agent = AgenticRAG()

        # 그래프에 노드가 있는지 확인
        assert agent.graph is not None
        # 컴파일된 그래프는 노드 정보 접근이 제한적이지만 실행 가능해야 함
        assert callable(agent.graph.invoke)
