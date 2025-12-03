# src/law_api.py
import requests
from src.config import LAW_API_SERVICE, LAW_API_SEARCH, LAW_API_OC, LAW_KEY

def format_jo_number(article_str: str) -> str:
    """조문 번호를 6자리 형식으로 변환"""
    numbers = ''.join(filter(str.isdigit, article_str))
    
    if not numbers:
        return "000000"
    
    if "의" in article_str:
        parts = article_str.replace("제", "").replace("조", "").split("의")
        jo = int(parts[0])
        gaji = int(parts[1]) if len(parts) > 1 else 0
        return f"{jo:04d}{gaji:02d}"
    else:
        jo = int(numbers)
        return f"{jo:04d}00"


def search_law_list(law_name: str) -> dict:
    """법령 목록 검색 (MST 찾기용)"""
    params = {
        'OC': LAW_API_OC,
        'target': 'law',
        'type': 'JSON',
        'query': law_name,
    }
    
    try:
        response = requests.get(LAW_API_SEARCH, params=params, timeout=10)
        
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}"}
        
        return response.json()
    
    except Exception as e:
        return {"error": f"검색 실패: {str(e)}"}


def get_law_detail(mst: str, target_type: str = '시행일 본문') -> dict:
    """법령 전체 본문 조회"""
    target_code = LAW_KEY.get(target_type, LAW_KEY['시행일 본문'])
    
    params = {
        'OC': LAW_API_OC,
        'target': target_code,
        'type': 'JSON',
        'MST': mst,
    }
    
    try:
        response = requests.get(LAW_API_SERVICE, params=params, timeout=10)
        
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}"}
        
        return response.json()
    
    except Exception as e:
        return {"error": f"본문 조회 실패: {str(e)}"}


def get_law_article(mst: str, jo: str, target_type: str = '시행일 본문') -> dict:
    """특정 조문만 조회"""
    target_code = LAW_KEY.get(target_type, LAW_KEY['시행일 본문'])
    
    params = {
        'OC': LAW_API_OC,
        'target': target_code,
        'type': 'JSON',
        'MST': mst,
        'JO': jo,
    }
    
    try:
        response = requests.get(LAW_API_SERVICE, params=params, timeout=10)
        
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}"}
        
        return response.json()
    
    except Exception as e:
        return {"error": f"조문 조회 실패: {str(e)}"}


def search_and_get_law(law_name: str, article_num: str = None) -> dict:
    """법령명으로 검색 → MST 추출 → 본문 조회"""
    
    law_name_map = {
        "헌법": "대한민국헌법",
        "민법": "민법",
        "형법": "형법",
        "근로기준법": "근로기준법",
        "상법": "상법",
        "주택임대차보호법": "주택임대차보호법",
    }
    
    formal_name = law_name_map.get(law_name, law_name)
    
    # Step 1: 법령 검색
    search_result = search_law_list(formal_name)
    
    if "error" in search_result:
        return search_result
    
    # Step 2: MST 추출
    try:
        law_search = search_result.get("LawSearch", {})
        law_list = law_search.get("law", [])
        
        # 리스트가 아니면 리스트로 변환
        if isinstance(law_list, dict):
            law_list = [law_list]
        
        if not law_list:
            return {"error": "법령을 찾을 수 없습니다."}
        
        # 정확한 법령명 매칭 (중요!)
        law_info = None
        for law in law_list:
            law_name_in_result = law.get("법령명한글", "")
            
            # 정확히 일치하는 법령 찾기
            if law_name_in_result == formal_name:
                law_info = law
                break
        
        # 정확한 매칭 없으면 첫 번째 사용
        if not law_info:
            print(f"⚠️ 정확한 매칭 실패, 첫 번째 결과 사용: {law_list[0].get('법령명한글')}")
            law_info = law_list[0]
        
        mst = law_info.get("법령일련번호")
        
        if not mst:
            return {"error": "법령일련번호를 찾을 수 없습니다."}
        
        print(f"✅ 법령 매칭: {law_info.get('법령명한글')} (MST: {mst})")
        
        # Step 3: 본문 조회
        if article_num:
            jo_formatted = format_jo_number(article_num)
            return get_law_article(mst, jo_formatted)
        else:
            return get_law_detail(mst)
    
    except Exception as e:
        import traceback
        return {"error": f"파싱 오류: {str(e)}", "trace": traceback.format_exc()}


def extract_article_content(law_data: dict) -> str:
    """조문 API 응답에서 내용 추출"""
    if "error" in law_data:
        return f"오류: {law_data['error']}"
    
    try:
        law = law_data.get("법령", {})
        articles_data = law.get("조문", {})
        articles = articles_data.get("조문단위", [])
        
        # 리스트가 아니면 리스트로 변환
        if isinstance(articles, dict):
            articles = [articles]
        elif not isinstance(articles, list):
            return "예상치 못한 응답 형식입니다."
        
        if not articles:
            return "조문 정보를 찾을 수 없습니다."
        
        # 조문 처리
        result_parts = []
        
        for article in articles:
            # article이 dict인지 확인
            if not isinstance(article, dict):
                continue
            
            jo_type = article.get("조문여부", "")
            
            # "조문"만 처리
            if jo_type == "조문":
                jo_num = article.get("조문내용", "제목 없음")
                hang_list = article.get("항", [])
                
                if hang_list and isinstance(hang_list, list):
                    contents = []
                    for hang in hang_list:
                        if isinstance(hang, dict):
                            hang_content = hang.get("항내용", "")
                            contents.append(hang_content)
                    
                    if contents:
                        full_content = "\n".join(contents)
                        result_parts.append(f"{jo_num}\n{full_content}")
                    else:
                        result_parts.append(f"{jo_num}: 내용 없음")
                else:
                    # 항이 없는 경우 조문내용 자체를 출력
                    jo_content = article.get("조문내용", "")
                    if isinstance(jo_content, str) and len(jo_content) > 10:
                        result_parts.append(jo_content)
                    else:
                        result_parts.append(f"{jo_num}: 내용 없음")
        
        if not result_parts:
            return "조문을 찾을 수 없습니다."
        
        return "\n\n".join(result_parts)
    
    except Exception as e:
        import traceback
        return f"조문 파싱 오류: {str(e)}\n{traceback.format_exc()}"


def get_law_content(law_name: str, article: str) -> str:
    """법령명 + 조문 조회
    
    Args:
        law_name: 법령명 (예: "헌법", "민법")
        article: 조문 번호 (예: "제1조", "제750조")
    
    Returns:
        조문 내용
    """
    law_data = search_and_get_law(law_name, article)
    return extract_article_content(law_data)


# 테스트
if __name__ == "__main__":
    import json
    
    print("="*60)
    print("민법 검색 결과 전체")
    print("="*60)
    
    search_result = search_law_list("민법")
    law_list = search_result.get("LawSearch", {}).get("law", [])
    
    if isinstance(law_list, list):
        print(f"\n총 {len(law_list)}개 결과:")
        for i, law in enumerate(law_list[:10]):  # 처음 10개만
            print(f"{i+1}. {law.get('법령명한글')} (MST: {law.get('법령일련번호')})")
    
    print("\n" + "="*60)
    print("TEST 1: 헌법 제1조")
    print("="*60)
    result1 = get_law_content("헌법", "제1조")
    print(result1)
    
    print("\n" + "="*60)
    print("TEST 2: 민법 제750조")
    print("="*60)
    result2 = get_law_content("민법", "제750조")
    print(result2)
    
    print("\n" + "="*60)
    print("TEST 3: 근로기준법 제56조")
    print("="*60)
    result3 = get_law_content("근로기준법", "제56조")
    print(result3)