# test.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from law_tools import get_specific_law_article, search_law_by_situation

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0)

tools = [get_specific_law_article, search_law_by_situation]

prompt = ChatPromptTemplate.from_messages([
    ("system", "너는 법률 상담 AI야. 적절한 도구를 선택해서 답변해."),
    ("human", "{input}"),
    ("placeholder", "{agent_scratchpad}"),
])

agent = create_tool_calling_agent(llm, tools, prompt)
executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 테스트 1: 구체적 조문
print("=" * 50)
response1 = executor.invoke({"input": "헌법 제1조 1항이 뭐야?"})
print(response1['output'])

# 테스트 2: 상황 설명
print("=" * 50)
response2 = executor.invoke({"input": "소 소유권 분쟁 어떡해?"})
print(response2['output'])

# 테스트 3: 애매한 질문 (LLM이 판단)
print("=" * 50)
response3 = executor.invoke({"input": "민법에서 불법행위 관련된 거 알려줘"})
print(response3['output'])