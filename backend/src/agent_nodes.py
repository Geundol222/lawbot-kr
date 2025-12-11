"""
Agent 노드 구현
- call_agent: LLM에게 도구 선택 요청
- execute_tools: 선택된 도구 실행
- should_continue: 도구 실행 계속 여부 판단
"""

import time
from typing import List
from langchain_core.messages import (
    HumanMessage,
    ToolMessage,
    convert_to_messages,
)
from src.agent_state import AgentState


class AgentNodes:
    """Agent 노드 로직을 담당하는 클래스"""

    def __init__(self, llm_with_tools, tools, wandb_logger=None):
        """
        Args:
            llm_with_tools: 도구가 바인딩된 LLM
            tools: 사용 가능한 도구 리스트
            wandb_logger: WandB 로거 (선택)
        """
        self.llm_with_tools = llm_with_tools
        self.tools = tools
        self.wandb_logger = wandb_logger

    def call_agent(self, state: AgentState) -> AgentState:
        """Agent 호출 - LLM이 도구를 선택"""
        agent_start = time.time()

        # LangGraph 상태가 dict/list 등으로 변할 수 있어 확실히 BaseMessage로 변환
        messages = convert_to_messages(state['messages'])

        # 방어적으로 사람이 쓴 메시지가 없으면 에러 방지
        has_human = any(
            isinstance(m, HumanMessage) or getattr(m, "type", "") == "human"
            for m in messages
        )
        if not has_human:
            messages.append(HumanMessage(content=state.get("question", "")))

        # LLM이 도구 선택!
        print("🤖 LLM 호출 중 (도구 선택)...")
        llm_start = time.time()
        response = self.llm_with_tools.invoke(messages)
        llm_time = time.time() - llm_start
        print(f"   ⏱️  LLM 응답: {llm_time:.2f}초")

        tool_calls_count = state.get("tool_calls", 0)
        if getattr(response, "tool_calls", None):
            # 도구 호출 개수만큼 카운트 증가
            num_calls = len(response.tool_calls)
            tool_calls_count += num_calls
            print(f"   → {num_calls}개 도구 호출 예정")

        agent_time = time.time() - agent_start
        print(f"⏱️  Agent 노드 완료: {agent_time:.2f}초")

        # 메시지 추가
        return {
            "messages": messages + [response],
            "question": state.get("question", ""),
            "tool_calls": tool_calls_count,
        }

    def execute_tools(self, state: AgentState) -> AgentState:
        """도구 실행 (ToolNode 대체)"""
        messages = state['messages']
        last_message = messages[-1]

        # 도구 호출 실행
        tool_messages = []
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                tool_name = tool_call['name']
                tool_args = tool_call['args']
                tool_id = tool_call['id']

                print(f"🔧 도구 호출: {tool_name}({', '.join(f'{k}={v}' for k, v in tool_args.items())})")

                # 도구 실행
                for tool in self.tools:
                    if tool.name == tool_name:
                        start_time = time.time()
                        success = True
                        result_str = ""

                        try:
                            result = tool.invoke(tool_args)
                            result_str = str(result)
                            tool_messages.append(
                                ToolMessage(
                                    content=result_str,
                                    tool_call_id=tool_id
                                )
                            )
                        except Exception as e:
                            success = False
                            result_str = f"도구 실행 오류: {str(e)}"
                            tool_messages.append(
                                ToolMessage(
                                    content=result_str,
                                    tool_call_id=tool_id
                                )
                            )

                        execution_time = time.time() - start_time
                        print(f"   ⏱️  도구 실행 완료: {execution_time:.2f}초")

                        # WandB 로깅
                        if self.wandb_logger:
                            self.wandb_logger.log_tool_call(
                                tool_name=tool_name,
                                args=tool_args,
                                result_preview=result_str[:200],
                                execution_time=execution_time,
                                success=success
                            )

                        break

        return {
            "messages": messages + tool_messages,
            "question": state.get("question", ""),
            "tool_calls": state.get("tool_calls", 0),
        }

    def should_continue(self, state: AgentState) -> str:
        """도구 실행 필요 여부 판단"""
        messages = state['messages']
        last_message = messages[-1]

        # 무한 루프 방지: 최대 10회 (벡터검색 → 조문조회 → API검색 → 재시도)
        if state.get("tool_calls", 0) >= 10:
            print("⚠️ 최대 도구 호출 횟수 도달, 종료합니다.")
            return "end"

        # ⭐ Function Calling 확인 ⭐
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "continue"

        return "end"
