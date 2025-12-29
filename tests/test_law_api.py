"""
법령 API 클라이언트 테스트
"""

import pytest
from unittest.mock import patch, MagicMock
from backend.src.law_api import (
    search_law_list,
    get_law_article,
    get_law_detail,
    format_jo_number,
    extract_article_content
)


@pytest.mark.unit
class TestFormatJoNumber:
    """조문 번호 포맷팅 테스트"""

    def test_format_with_je(self):
        """'제' 포함된 경우"""
        assert format_jo_number("제56조") == "005600"
        assert format_jo_number("제1조") == "000100"
        assert format_jo_number("제100조") == "010000"

    def test_format_without_je(self):
        """'제' 없는 경우"""
        assert format_jo_number("56조") == "005600"
        assert format_jo_number("1조") == "000100"

    def test_format_only_number(self):
        """숫자만 있는 경우"""
        assert format_jo_number("56") == "005600"
        assert format_jo_number("1") == "000100"


@pytest.mark.unit
class TestExtractArticleContent:
    """조문 내용 추출 테스트"""

    def test_extract_normal_content(self):
        """정상 조문 데이터"""
        law_data = {
            "법령": {
                "조문": {
                    "조문위치": [
                        {
                            "조문종류명": "조문",
                            "조문내용": "사용자는 연장근로에 대하여 통상임금의 50% 이상을 가산하여 지급하여야 한다."
                        }
                    ]
                }
            }
        }
        result = extract_article_content(law_data)
        assert "통상임금의 50%" in result

    def test_extract_list_format(self):
        """리스트 형식 조문"""
        law_data = {
            "법령": {
                "조문": {
                    "조문위치": [
                        {"조문종류명": "조문", "조문내용": "첫 번째 조문"},
                        {"조문종류명": "조문", "조문내용": "두 번째 조문"}
                    ]
                }
            }
        }
        result = extract_article_content(law_data)
        assert "첫 번째 조문" in result

    def test_extract_empty_data(self):
        """빈 데이터"""
        result = extract_article_content({})
        assert "조문 정보를 찾을 수 없습니다" in result

    def test_extract_error_response(self):
        """에러 응답"""
        law_data = {"error": "API 오류"}
        result = extract_article_content(law_data)
        assert "오류" in result


@pytest.mark.integration
class TestLawAPIIntegration:
    """법령 API 통합 테스트 (실제 API 호출)"""

    @pytest.mark.slow
    def test_search_real_law(self):
        """실제 근로기준법 검색"""
        result = search_law_list("근로기준법")

        assert "error" not in result
        assert "LawSearch" in result
        laws = result["LawSearch"].get("law", [])

        # 리스트 또는 딕셔너리 모두 처리
        if isinstance(laws, dict):
            laws = [laws]

        assert len(laws) > 0
        assert any("근로기준법" in law.get("법령명한글", "") for law in laws)

    @pytest.mark.slow
    def test_get_real_article(self):
        """실제 조문 조회 (근로기준법 제56조)"""
        # 먼저 법령 검색
        search_result = search_law_list("근로기준법")
        laws = search_result["LawSearch"]["law"]
        if isinstance(laws, dict):
            laws = [laws]

        mst = laws[0]["법령일련번호"]

        # 조문 조회
        article_data = get_law_article(mst=mst, jo="0056")
        content = extract_article_content(article_data)

        assert content
        assert "오류" not in content
        assert len(content) > 0
