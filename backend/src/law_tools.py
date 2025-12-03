from langchain.tools import tool
from src.law_api import get_law_content, search_law_list
from src.config import get_llm

@tool
def get_specific_law_article(law_name: str, article: str) -> str:
    """특정 법령의 조문을 정확히 조회합니다."""
    try:
        result = get_law_content(law_name, article)
        return result
    except Exception as e:
        return f"오류: {str(e)}"


@tool
def search_law_by_situation(situation: str) -> str:
    """법률 상황별 검색 - API로 MST 찾기!"""
    try:
        llm = get_llm()
        
        # Step 1: LLM이 법령명 추출
        law_name_prompt = f"""다음 상황과 관련된 한국 법령명을 1~2개만 정확히 출력해줘.

상황: {situation}

예시:
- "야근수당" → 근로기준법
- "소유권 분쟁" → 민법
- "월세 해지" → 주택임대차보호법

정확한 법령명만 쉼표로 구분:
"""
        
        response = llm.invoke(law_name_prompt)
        law_names = [name.strip() for name in response.content.strip().split(",")]
        
        print(f"🔍 추출된 법령명: {law_names}")
        
        # Step 2: API로 검색해서 MST 가져오기!
        found_laws = []
        
        for law_name in law_names[:2]:
            result = search_law_list(law_name)
            
            if "error" not in result:
                law_list = result.get("LawSearch", {}).get("law", [])
                
                if isinstance(law_list, dict):
                    law_list = [law_list]
                
                # ⭐ 핵심: 정확히 일치하는 것만 추출! ⭐
                for law in law_list:
                    searched_name = law.get("법령명한글", "")
                    
                    # 완전 일치만!
                    if searched_name == law_name:
                        found_laws.append({
                            "법령명": searched_name,
                            "MST": law.get("법령일련번호", ""),
                            "법령ID": law.get("법령ID", ""),
                        })
                        print(f"✅ 매칭 성공: {searched_name} (MST: {law.get('법령일련번호')})")
                        break  # 정확한 거 찾으면 종료
        
        if not found_laws:
            return f"'{situation}'와 관련된 법령을 찾지 못했습니다."
        
        # 결과 반환 (법령명만, MST는 내부적으로 확인됨)
        result_text = "관련 법령:\n"
        for law in found_laws:
            result_text += f"- {law['법령명']}\n"
        
        return result_text
    
    except Exception as e:
        import traceback
        return f"검색 오류: {str(e)}\n{traceback.format_exc()}"