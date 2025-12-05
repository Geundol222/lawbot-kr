# src/law_api_monitored.py
"""
law_api.py의 모니터링 래퍼
- 원본 law_api.py는 수정하지 않음
- 이 파일에서 WandB 로깅 추가
"""
import time
from src.law_api import *
from src.monitoring import get_wandb_logger, LawAPILogger

# 로거 초기화
try:
    _law_api_logger = LawAPILogger(get_wandb_logger())
except Exception:
    _law_api_logger = None


def search_law_list_monitored(law_name: str) -> dict:
    """법령 목록 검색 (모니터링 추가)"""
    start_time = time.time()

    result = search_law_list(law_name)

    response_time = time.time() - start_time
    success = "error" not in result
    error_msg = result.get("error") if not success else None

    # WandB 로깅
    if _law_api_logger:
        _law_api_logger.log_api_call(
            endpoint="search_law_list",
            law_name=law_name,
            article=None,
            response_time=response_time,
            status_code=200 if success else 500,
            success=success,
            error_message=error_msg
        )

    return result


def get_law_article_monitored(mst: str, jo: str, target_type: str = '시행일 본문') -> dict:
    """특정 조문 조회 (모니터링 추가)"""
    start_time = time.time()

    result = get_law_article(mst, jo, target_type)

    response_time = time.time() - start_time
    success = "error" not in result
    error_msg = result.get("error") if not success else None

    # WandB 로깅
    if _law_api_logger:
        _law_api_logger.log_api_call(
            endpoint="get_law_article",
            law_name=mst,
            article=jo,
            response_time=response_time,
            status_code=200 if success else 500,
            success=success,
            error_message=error_msg
        )

    return result


def get_law_detail_monitored(mst: str, target_type: str = '시행일 본문') -> dict:
    """법령 전체 본문 조회 (모니터링 추가)"""
    start_time = time.time()

    result = get_law_detail(mst, target_type)

    response_time = time.time() - start_time
    success = "error" not in result
    error_msg = result.get("error") if not success else None

    # WandB 로깅
    if _law_api_logger:
        _law_api_logger.log_api_call(
            endpoint="get_law_detail",
            law_name=mst,
            article=None,
            response_time=response_time,
            status_code=200 if success else 500,
            success=success,
            error_message=error_msg
        )

    return result
