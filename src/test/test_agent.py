# test_simple.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from src.test.law_tools import get_specific_law_article, search_law_by_situation
from src.config import get_llm

llm = get_llm()

# 도구 바인딩
tools = [get_specific_law_article, search_law_by_situation]
llm_with_tools = llm.bind_tools(tools)

# ============================================
# 여러 질문 테스트 함수
# ============================================
def run_agent(question: str):
    """질문을 받아서 도구 호출 + 답변 생성"""
    
    # 시스템 메시지 추가
    messages = [
        {
            "role": "system",
            "content": """당신은 한국 법률 상담 AI입니다.

사용자의 질문을 분석해서 **반드시 도구를 선택**해야 합니다:

1. **get_specific_law_article**: 
   - "헌법 제X조", "민법 제X조"처럼 구체적인 조문명이 있을 때
   - 예: "헌법 1조 1항 뭐야?", "민법 750조 알려줘"

2. **search_law_by_situation**: 
   - 법령명 없이 상황, 문제, 질문을 설명할 때
   - 예: "소 소유권 분쟁 어떡해?", "야근수당 안 줘", "환불 거부당했어요"
   
불완전한 문장이나 구어체 질문도 모두 **search_law_by_situation**으로 처리하세요.
도구를 선택하지 않으면 안 됩니다!"""
        },
        {
            "role": "user",
            "content": question
        }
    ]
    
    # 1. LLM이 도구 선택
    response = llm_with_tools.invoke(messages)
    
    print(f"LLM의 도구 호출: {response.tool_calls}")
    
    # 2. 도구 실행
    if response.tool_calls:
        tool_call = response.tool_calls[0]
        tool_name = tool_call['name']
        tool_args = tool_call['args']
        
        print(f"호출할 도구: {tool_name}")
        print(f"파라미터: {tool_args}")
        
        # 도구 실행
        if tool_name == "get_specific_law_article":
            result = get_specific_law_article.invoke(tool_args)
        elif tool_name == "search_law_by_situation":
            result = search_law_by_situation.invoke(tool_args)
        
        print(f"결과: {result}")
        
        # 3. 최종 답변 생성
        final_response = llm.invoke(
            f"질문: {question}\n검색 결과: {result}\n\n위 정보로 답변해줘."
        )
        
        return final_response.content
    
    else:
        # 도구 선택 안 했을 때 재시도
        print("\n⚠️ 도구 선택 실패! 재시도 중...")
        
        retry_response = llm_with_tools.invoke([
            {
                "role": "system",
                "content": "사용자의 질문은 법률 상담입니다. 반드시 search_law_by_situation 도구를 사용하세요."
            },
            {
                "role": "user", 
                "content": question
            }
        ])
        
        if retry_response.tool_calls:
            tool_call = retry_response.tool_calls[0]
            result = search_law_by_situation.invoke(tool_call['args'])
            final_response = llm.invoke(f"질문: {question}\n검색 결과: {result}\n\n위 정보로 답변해줘.")
            return final_response.content
        
        return "죄송합니다. 질문을 이해하지 못했습니다. 좀 더 구체적으로 말씀해주세요."


# ============================================
# 여기부터 추가된 부분!
# ============================================
if __name__ == "__main__":
    
    test_cases = [
        "헌법 제1조 1항이 뭐야?",           # 구체적 조문
        "민법 제750조 알려줘",              # 구체적 조문
        "소 소유권 분쟁 어떡해?",           # 상황 - 완전한 문장
        "회사가 야근수당 안 주는데?",       # 상황 - 불완전한 문장
        "월세 계약 해지하고 싶어",          # 상황 - 동사형
        "교통사고 났는데 보험처리",         # 상황 - 초간단
    ]
    
    for question in test_cases:
        print("\n" + "="*60)
        print(f"질문: {question}")
        print("="*60)
        
        answer = run_agent(question)
        
        print(f"\n최종 답변:\n{answer}")
        print("="*60)