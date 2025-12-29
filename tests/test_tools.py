"""
Agent Tools 단위 테스트
"""

import pytest
from unittest.mock import patch, MagicMock
from backend.src.agentic_rag import search_vector_db, get_full_article_content, search_law_by_api


@pytest.mark.unit
class TestSearchVectorDB:
    """search_vector_db 도구 테스트"""

    @patch("backend.src.agentic_rag.vector_search_instance")
    def test_search_success(self, mock_vector_search, sample_vector_search_results):
        """벡터 검색 성공 케이스"""
        mock_vector_search.search.return_value = sample_vector_search_results

        result = search_vector_db.invoke({"query": "야근수당"})

        assert "근로기준법" in result
        assert "제56조" in result
        assert "유사도: 0.85" in result
        assert "내용:" in result
        assert "추가 도구 호출 불필요" in result

    @patch("backend.src.agentic_rag.vector_search_instance")
    def test_search_no_match(self, mock_vector_search):
        """벡터 검색 실패 케이스 (유사도 낮음)"""
        mock_vector_search.search.return_value = []

        result = search_vector_db.invoke({"query": "존재하지 않는 법령"})

        assert "VECTOR_DB_NO_MATCH" in result
        assert "search_law_by_api" in result


@pytest.mark.unit
class TestGetFullArticleContent:
    """get_full_article_content 도구 테스트"""

    @patch("backend.src.agentic_rag.get_law_article")
    @patch("backend.src.agentic_rag.extract_article_content")
    def test_get_article_success(self, mock_extract, mock_get_law):
        """조문 가져오기 성공"""
        mock_extract.return_value = "조문 내용입니다."

        result = get_full_article_content.invoke({
            "law_name": "근로기준법",
            "article": "제56조",
            "mst": "001234"
        })

        assert "근로기준법" in result
        assert "제56조" in result
        assert "조문 내용입니다" in result

    def test_get_article_no_mst(self):
        """MST 없을 때"""
        result = get_full_article_content.invoke({
            "law_name": "근로기준법",
            "article": "제56조",
            "mst": ""
        })

        assert "MST(법령일련번호) 정보가 없어" in result


@pytest.mark.unit
class TestSearchLawByAPI:
    """search_law_by_api 도구 테스트"""

    @patch("backend.src.agentic_rag.get_law_article")
    @patch("backend.src.agentic_rag.extract_article_content")
    @patch("backend.src.agentic_rag.search_law_list")
    def test_search_specific_article(self, mock_search, mock_extract, mock_get_law):
        """특정 조문 검색"""
        mock_search.return_value = {
            "LawSearch": {
                "law": {
                    "법령명한글": "근로기준법",
                    "법령일련번호": "001234"
                }
            }
        }
        mock_extract.return_value = "조문 내용입니다."

        result = search_law_by_api.invoke({
            "law_name": "근로기준법",
            "article_number": "56조"
        })

        assert "근로기준법" in result
        assert "조문 내용입니다" in result

    @patch("backend.src.agentic_rag.search_law_list")
    def test_search_law_not_found(self, mock_search):
        """법령 검색 실패"""
        mock_search.return_value = {
            "LawSearch": {
                "law": []
            }
        }

        result = search_law_by_api.invoke({
            "law_name": "존재하지않는법",
            "article_number": ""
        })

        assert "찾을 수 없습니다" in result

    @patch("backend.src.agentic_rag.search_law_list")
    def test_search_api_error(self, mock_search):
        """API 오류"""
        mock_search.return_value = {
            "error": "API 오류"
        }

        result = search_law_by_api.invoke({
            "law_name": "근로기준법",
            "article_number": ""
        })

        assert "법령 검색 실패" in result
