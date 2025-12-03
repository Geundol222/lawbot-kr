# src/agent.py
import time
from langchain_google_genai import ChatGoogleGenerativeAI
from src.law_tools import get_specific_law_article, search_law_by_situation
from src.config import get_llm

llm = get_llm()

# 도구 바인딩
tools = [get_specific_law_article, search_law_by_situation]
llm_with_tools = llm.bind_tools(tools)

def run_agent(question: str):
    """질문 처리"""
    
    messages = [
        {
            "role": "system",
            "content": """당신은 한국 법률 상담 AI입니다.

**반드시 도구를 선택해야 합니다!**

1. **get_specific_law_article**: 
   - "헌법 제X조", "민법 제X조"처럼 **법령명 + 조문 번호**가 명확할 때
   - 예: "헌법 1조", "민법 750조"

2. **search_law_by_situation**: 
   - **법령명이나 조문 번호 없이** 상황/문제만 설명할 때
   - 예: "야근수당 안 줘", "월세 해지하고 싶어", "교통사고 났어"
   
**중요:** 
- "~하고 싶어", "~어떡해?", "~인데?" 같은 질문은 모두 search_law_by_situation!
- 도구를 선택하지 않으면 안 됩니다!"""
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
        else:
            result = "알 수 없는 도구"
        
        print(f"결과: {result}")
        
        # 3. 최종 답변 생성
        final_response = llm.invoke(
            f"질문: {question}\n검색 결과: {result}\n\n위 정보로 답변해줘."
        )
        
        return final_response.content  # ← 이게 중요!
    
    else:
        return "죄송합니다. 질문을 이해하지 못했습니다."


if __name__ == "__main__":
    
    test_cases = [
        "헌법 제1조 1항이 뭐야?",
        "민법 제750조 알려줘",
        "소 소유권 분쟁 어떡해?",
        "회사가 야근수당 안 주는데?",
        "월세 계약 해지하고 싶어",
        "교통사고 났는데 보험처리",
    ]
    
    for i, question in enumerate(test_cases, 1):
        print("\n" + "="*60)
        print(f"질문: {question}")
        print("="*60)
        
        answer = run_agent(question)
        
        print(f"\n최종 답변:\n{answer}")
        print("="*60)
        
        # Rate Limit 방지
        if i < len(test_cases):
            print("\n⏳ Rate Limit 방지 대기 중... (7초)")
            time.sleep(7)