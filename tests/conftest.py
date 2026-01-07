"""
pytest 공통 설정 및 fixtures
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock

# backend/src를 import 경로에 추가 (src.* 모듈 인식)
ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture(scope="session")
def test_env():
    """테스트용 환경 변수 설정"""
    os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY", "test_google_key")
    os.environ["SUPABASE_URL"] = os.getenv("SUPABASE_URL", "https://test.supabase.co")
    os.environ["SUPABASE_ANON_KEY"] = os.getenv("SUPABASE_ANON_KEY", "test_anon_key")
    os.environ["LAW_API_OC"] = os.getenv("LAW_API_OC", "test_law_api_key")
    os.environ["WANDB_ENABLED"] = "false"
    yield


@pytest.fixture
def mock_supabase_client():
    """Supabase 클라이언트 Mock"""
    mock = MagicMock()
    mock.table.return_value.select.return_value.execute.return_value.data = []
    return mock


@pytest.fixture
def sample_law_data():
    """테스트용 법령 데이터"""
    return {
        "law_name": "근로기준법",
        "article": "제56조",
        "mst": "001234",
        "content": "사용자는 연장근로에 대하여는 통상임금의 100분의 50 이상을 가산하여 근로자에게 지급하여야 한다.",
        "similarity": 0.85
    }


@pytest.fixture
def sample_vector_search_results(sample_law_data):
    """벡터 검색 결과 샘플"""
    return [sample_law_data]


@pytest.fixture
def sample_api_response():
    """법령 API 응답 샘플"""
    return {
        "LawSearch": {
            "law": [
                {
                    "법령명한글": "근로기준법",
                    "법령일련번호": "001234"
                }
            ]
        }
    }
