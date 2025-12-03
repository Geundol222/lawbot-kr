# src/test/law_tools.py
from langchain.tools import tool
from src.law_api import get_law_content, search_and_get_law

@tool
def get_specific_law_article(law_name: str, article: str) -> str:
    """특정 법령의 조문을 정확히 조회합니다.
    
    이 도구는 사용자가 **명확한 법령명과 조문 번호**를 언급했을 때 사용합니다.
    
    예시:
    - "헌법 제1조 1항이 뭐야?"
    - "민법 750조 알려줘"
    - "형법 제250조 내용"
    
    Args:
        law_name: 법령 이름 (예: "헌법", "민법", "형법")
        article: 조문 번호 (예: "제1조", "제750조")
    
    Returns:
        해당 조문의 전체 내용
    """
    try:
        result = get_law_content(law_name, article)
        return result
    except Exception as e:
        return f"오류가 발생했습니다: {str(e)}"


@tool
def search_law_by_situation(situation: str) -> str:
    """법률 상황이나 문제를 설명하면 관련 법령을 찾아줍니다.
    
    이 도구는 사용자가 **구체적인 법령명 없이 상황이나 문제를 설명**했을 때 사용합니다.
    
    예시:
    - "소 소유권 분쟁 어떡해?"
    - "회사가 야근수당 안 주는데?"
    - "이웃집 소음이 너무 심해요"
    - "온라인 쇼핑몰에서 환불 거부당했어요"
    
    Args:
        situation: 사용자의 법률 문제나 상황 설명
    
    Returns:
        관련 법령 및 조문 정보
    """
    # TODO: LLM 키워드 추출 + 법령 검색
    # 나중에 구현!
    return f"[상황별 법률 검색] '{situation}'에 관한 법령을 찾았습니다. (실제 구현 예정)"