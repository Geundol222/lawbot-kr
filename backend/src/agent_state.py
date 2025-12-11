"""
Agent 상태 정의
"""

from typing import TypedDict, List, Annotated


class AgentState(TypedDict):
    """Agent 실행 상태"""
    messages: Annotated[List, "messages"]
    question: str
    tool_calls: int  # 방어용: 무한 반복 방지
