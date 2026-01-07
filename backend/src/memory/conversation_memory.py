"""
대화 이력 메모리 관리
- Buffer Memory: 세션 내 대화 맥락 유지
- Supabase 연동: 이전 대화 불러오기
"""

from typing import List, Dict, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from datetime import datetime


class ConversationMemory:
    """세션별 대화 이력 관리"""

    def __init__(self, session_id: str, max_messages: int = 10):
        """
        Args:
            session_id: 세션 ID
            max_messages: 최대 메시지 수 (메모리 제한, 기본 10턴 = 20 메시지)
        """
        self.session_id = session_id
        self.max_messages = max_messages * 2  # Human + AI = 2 messages per turn
        self.messages: List = []

    def add_user_message(self, content: str):
        """사용자 메시지 추가"""
        self.messages.append(HumanMessage(content=content))
        self._trim_messages()

    def add_ai_message(self, content: str):
        """AI 답변 추가"""
        self.messages.append(AIMessage(content=content))
        self._trim_messages()

    def get_messages(self) -> List:
        """현재 메시지 이력 반환"""
        return self.messages

    def get_context_string(self) -> str:
        """이전 대화를 텍스트로 변환 (프롬프트 컨텍스트용)"""
        if not self.messages:
            return ""

        context_parts = []
        for msg in self.messages:
            if isinstance(msg, HumanMessage):
                context_parts.append(f"사용자: {msg.content}")
            elif isinstance(msg, AIMessage):
                context_parts.append(f"AI: {msg.content}")

        return "\n".join(context_parts)

    def clear(self):
        """메시지 초기화"""
        self.messages = []

    def _trim_messages(self):
        """메시지 수 제한 (최신 N개만 유지)"""
        if len(self.messages) > self.max_messages:
            # 시스템 메시지는 유지, 나머지는 최신 것만
            system_messages = [m for m in self.messages if isinstance(m, SystemMessage)]
            other_messages = [m for m in self.messages if not isinstance(m, SystemMessage)]

            # 최신 max_messages개만 유지
            other_messages = other_messages[-self.max_messages:]

            self.messages = system_messages + other_messages


class SupabaseConversationMemory(ConversationMemory):
    """Supabase 연동 대화 메모리 (이전 대화 불러오기)"""

    def __init__(self, session_id: str, supabase_client, max_messages: int = 10, load_previous: bool = True):
        """
        Args:
            session_id: 세션 ID
            supabase_client: Supabase 클라이언트
            max_messages: 최대 메시지 수
            load_previous: 시작 시 이전 대화 불러오기 여부
        """
        super().__init__(session_id, max_messages)
        self.supabase = supabase_client

        if load_previous:
            self._load_previous_conversations()

    def _load_previous_conversations(self):
        """Supabase에서 이전 대화 불러오기"""
        try:
            # 세션의 최근 대화 조회 (최대 max_messages 턴)
            result = self.supabase.table("conversation_logs")\
                .select("user_question, bot_answer, created_at")\
                .eq("session_id", self.session_id)\
                .order("created_at", desc=False)\
                .limit(self.max_messages)\
                .execute()

            if result.data:
                for row in result.data:
                    # 사용자 질문
                    self.messages.append(HumanMessage(content=row["user_question"]))
                    # AI 답변
                    self.messages.append(AIMessage(content=row["bot_answer"]))

                print(f"✅ 이전 대화 불러오기 완료: {len(result.data)}턴 ({len(self.messages)}개 메시지)")

        except Exception as e:
            print(f"⚠️ 이전 대화 불러오기 실패: {e}")

    def add_and_save(self, user_question: str, bot_answer: str,
                     law_name: Optional[str] = None,
                     article: Optional[str] = None,
                     response_time_ms: Optional[int] = None):
        """
        메모리에 추가 + Supabase에 저장

        Args:
            user_question: 사용자 질문
            bot_answer: 봇 답변
            law_name: 법령명 (선택)
            article: 조문 (선택)
            response_time_ms: 응답 시간 (선택)
        """
        # 메모리 추가
        self.add_user_message(user_question)
        self.add_ai_message(bot_answer)

        # Supabase 저장
        try:
            # 세션이 존재하는지 확인하고, 없으면 생성
            session_check = self.supabase.table("sessions")\
                .select("*")\
                .eq("session_id", self.session_id)\
                .execute()

            if not session_check.data:
                # 세션이 없으면 생성
                self.supabase.table("sessions").insert({
                    "session_id": self.session_id
                }).execute()
                print(f"✅ 새 세션 생성: {self.session_id}")

            # 대화 로그 저장
            self.supabase.table("conversation_logs").insert({
                "session_id": self.session_id,
                "user_question": user_question,
                "bot_answer": bot_answer,
                "law_name": law_name,
                "article": article,
                "response_time_ms": response_time_ms
            }).execute()

            print(f"✅ 대화 저장 완료: {self.session_id}")

        except Exception as e:
            print(f"⚠️ 대화 저장 실패: {e}")


def create_conversation_memory(
    session_id: str,
    supabase_client=None,
    max_turns: int = 5,
    load_previous: bool = True
) -> ConversationMemory:
    """
    대화 메모리 팩토리 함수

    Args:
        session_id: 세션 ID
        supabase_client: Supabase 클라이언트 (None이면 기본 메모리만)
        max_turns: 최대 대화 턴 수 (기본 5턴 = 10 메시지)
        load_previous: 이전 대화 불러오기 여부

    Returns:
        ConversationMemory 또는 SupabaseConversationMemory
    """
    if supabase_client:
        return SupabaseConversationMemory(
            session_id=session_id,
            supabase_client=supabase_client,
            max_messages=max_turns,
            load_previous=load_previous
        )
    else:
        return ConversationMemory(
            session_id=session_id,
            max_messages=max_turns
        )
