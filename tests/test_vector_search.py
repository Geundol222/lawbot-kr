"""
벡터 검색 테스트
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from backend.src.embeddings.vector_search import VectorSearch


@pytest.mark.unit
class TestVectorSearchUnit:
    """VectorSearch 단위 테스트 (Mock 사용)"""

    @patch("backend.src.embeddings.vector_search.SentenceTransformer")
    @patch("backend.src.embeddings.vector_search.create_client")
    def test_search_with_results(self, mock_supabase, mock_model):
        """검색 결과가 있는 경우"""
        # Supabase Mock 설정
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_rpc_result = MagicMock()
        mock_rpc_result.data = [
            {
                "id": 1,
                "law_name": "근로기준법",
                "article": "제56조",
                "mst": "001234",
                "content": "연장근로 가산임금 규정",
                "similarity": 0.85
            }
        ]
        mock_client.rpc.return_value = mock_rpc_result

        # 임베딩 모델 Mock
        mock_model_instance = MagicMock()
        mock_model_instance.encode.return_value = [0.1] * 1024
        mock_model.return_value = mock_model_instance

        # 테스트 실행
        vs = VectorSearch()
        results = vs.search("야근수당", top_k=5, threshold=0.7)

        assert len(results) == 1
        assert results[0]["law_name"] == "근로기준법"
        assert results[0]["similarity"] >= 0.7

    @patch("backend.src.embeddings.vector_search.SentenceTransformer")
    @patch("backend.src.embeddings.vector_search.create_client")
    def test_search_no_results(self, mock_supabase, mock_model):
        """검색 결과가 없는 경우 (유사도 낮음)"""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_rpc_result = MagicMock()
        mock_rpc_result.data = []
        mock_client.rpc.return_value = mock_rpc_result

        mock_model_instance = MagicMock()
        mock_model_instance.encode.return_value = [0.1] * 1024
        mock_model.return_value = mock_model_instance

        vs = VectorSearch()
        results = vs.search("무관한 질문", top_k=5, threshold=0.7)

        assert len(results) == 0

    @patch("backend.src.embeddings.vector_search.SentenceTransformer")
    @patch("backend.src.embeddings.vector_search.create_client")
    def test_deduplicate_chunks(self, mock_supabase, mock_model):
        """청크 중복 제거 테스트"""
        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        # 같은 조문의 여러 청크
        mock_rpc_result = MagicMock()
        mock_rpc_result.data = [
            {
                "id": 1,
                "law_name": "민법",
                "article": "제750조_part1",
                "mst": "002345",
                "content": "내용 1",
                "similarity": 0.85
            },
            {
                "id": 2,
                "law_name": "민법",
                "article": "제750조_part2",
                "mst": "002345",
                "content": "내용 2",
                "similarity": 0.82
            },
            {
                "id": 3,
                "law_name": "민법",
                "article": "제751조",
                "mst": "002345",
                "content": "내용 3",
                "similarity": 0.80
            }
        ]
        mock_client.rpc.return_value = mock_rpc_result

        mock_model_instance = MagicMock()
        mock_model_instance.encode.return_value = [0.1] * 1024
        mock_model.return_value = mock_model_instance

        vs = VectorSearch()
        results = vs.search("불법행위", top_k=5, threshold=0.7)

        # 제750조는 하나만 남아야 함 (최고 유사도)
        article_750_count = sum(1 for r in results if "제750조" in r["article"])
        assert article_750_count == 1

        # 최고 유사도를 가진 청크만 남음
        article_750 = [r for r in results if "제750조" in r["article"]][0]
        assert article_750["similarity"] == 0.85


@pytest.mark.integration
@pytest.mark.slow
class TestVectorSearchIntegration:
    """VectorSearch 통합 테스트 (실제 Supabase 연결)"""

    def test_real_search(self, test_env):
        """실제 벡터 검색 (Supabase 연결 필요)"""
        # 환경 변수가 실제로 설정되어 있을 때만 실행
        import os
        if os.getenv("SUPABASE_URL") == "https://test.supabase.co":
            pytest.skip("실제 Supabase 환경 변수 필요")

        vs = VectorSearch()
        results = vs.search("야근수당", top_k=3, threshold=0.5)

        # 결과가 있으면 검증
        if results:
            assert all("law_name" in r for r in results)
            assert all("article" in r for r in results)
            assert all("similarity" in r for r in results)
            assert all(r["similarity"] >= 0.5 for r in results)
