"""
Agent 스트리밍 로직
- run_stream: 스트리밍 응답 생성
"""

import time
import asyncio
from uuid import uuid4
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage

from src.embeddings.vector_search import VectorSearch
from src.supabase_client import save_conversation


vector_search_instance = VectorSearch()


class AgentStreaming:
    """Agent 스트리밍 로직을 담당하는 클래스"""

    def __init__(self, graph, llm, wandb_logger=None):
        """
        Args:
            graph: 컴파일된 LangGraph
            llm: 답변 생성용 LLM
            wandb_logger: WandB 로거 (선택)
        """
        self.graph = graph
        self.llm = llm
        self.wandb_logger = wandb_logger

    def _run_stream_sync(self, question: str, session_id: str, start_time: float):
        """동기 스트리밍 로직 (간단하고 안정적)"""
        full_answer = ""

        # 초기 메시지
        initial_messages = [
            SystemMessage(
                content="""한국 법률 상담 AI입니다. 반드시 아래 단계를 따라 작업하세요:

1단계: search_vector_db(질문)로 벡터 DB 검색

2단계:
  A. 벡터 검색 성공 시 (유사도 0.7 이상):
     → 검색 결과에 "내용" 필드가 포함되어 있습니다
     → 즉시 해당 내용으로 답변 작성 (추가 도구 호출 금지!)
     → get_full_article_content 호출하지 마세요!

  B. 벡터 검색 실패 시 (VECTOR_DB_NO_MATCH):
     → search_law_by_api(법령명)로 API 검색
     → 예: "택배 분실" → search_law_by_api("전자상거래법")

3단계: 조회한 법령 내용으로 답변 작성

답변 형식:
- 요약
- 근거 법령 (법령명 + 조문)
- 조문 내용

중요 규칙:
1. 벡터 검색 결과에 "내용"이 있으면 바로 답변 작성! (API 호출 금지)
2. get_full_article_content는 특별한 경우에만 사용 (벡터 검색에서 내용이 없을 때)
3. 동일한 도구를 반복 호출하지 마세요"""
            ),
            HumanMessage(content=question)
        ]

        initial_state = {
            "messages": initial_messages,
            "question": question,
            "tool_calls": 0,
        }

        try:
            # 1단계: Tool calling 완료까지 실행 (non-streaming)
            graph_start = time.time()
            print("⏱️  그래프 실행 시작...")

            final_state = None
            for event in self.graph.stream(initial_state):
                final_state = event

            graph_time = time.time() - graph_start
            print(f"⏱️  그래프 실행 완료: {graph_time:.2f}초")

            # 마지막 상태에서 메시지 추출
            if not final_state:
                yield "오류: 응답을 생성할 수 없습니다."
                return

            # 가장 마지막 노드의 출력 가져오기
            last_node_output = list(final_state.values())[-1]
            messages = last_node_output.get("messages", [])

            # 마지막 메시지 확인
            last_msg = messages[-1]

            # 답변 텍스트 추출 (문자열 또는 리스트 형식 모두 처리)
            answer_text = None
            if hasattr(last_msg, 'content') and last_msg.content:
                content = last_msg.content

                # 문자열인 경우
                if isinstance(content, str):
                    answer_text = content
                # 리스트 형식인 경우 (Gemini 응답)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and 'text' in part:
                            answer_text = part['text']
                            break

            # 답변이 있으면 스트리밍
            if answer_text:
                print(f"📝 답변 생성 완료 ({len(answer_text)}자), 스트리밍 중...")

                # 1자씩 스트리밍 (자연스러운 타이핑 효과)
                for char in answer_text:
                    full_answer += char
                    yield char
                    # 약간의 딜레이로 자연스러운 속도 조절 (30ms)
                    time.sleep(0.03)
            else:
                # 답변이 없으면 LLM에게 직접 물어보기
                print(f"⚠️  답변 텍스트를 찾을 수 없음, LLM에게 답변 요청...")

                for chunk in self.llm.stream(messages):
                    chunk_text = ""
                    if hasattr(chunk, 'content'):
                        content = chunk.content
                        if not content:
                            continue

                        if isinstance(content, list):
                            for part in content:
                                if isinstance(part, dict) and 'text' in part:
                                    chunk_text += part['text']
                        elif isinstance(content, str):
                            chunk_text = content
                        else:
                            chunk_text = str(content)

                        if chunk_text:
                            full_answer += chunk_text
                            yield chunk_text

        except Exception as e:
            import traceback
            error_msg = f"\n\n❌ 오류 발생: {str(e)}\n"
            print(f"❌ 오류: {e}")
            print(f"❌ 상세 traceback:")
            traceback.print_exc()
            yield error_msg
            full_answer += error_msg

        print(f"\n{'='*60}")
        print(f"✅ 완료! (총 {len(full_answer)}자)")
        print(f"{'='*60}\n")

        # WandB 세션 종료 및 로깅
        if self.wandb_logger:
            total_tokens = len(question.split()) + len(full_answer.split())
            self.wandb_logger.end_session(full_answer, total_tokens)

        # Supabase 대화 로그 저장
        try:
            law_name = None
            article = None
            if vector_search_instance.last_results:
                top = vector_search_instance.last_results[0]
                law_name = top.get("law_name")
                article = top.get("article")

            save_conversation(
                session_id=session_id,
                user_question=question,
                bot_answer=full_answer,
                law_name=law_name,
                article=article,
                response_time_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            print(f"⚠️ Supabase 대화 저장 실패: {e}")

    def run_stream(self, question: str, session_id: Optional[str] = None):
        """Agent 실행 (streaming)"""
        start_time = time.time()
        print(f"\n{'='*60}")
        print(f"🤖 Agentic RAG 시작 (실시간 스트리밍)")
        print(f"❓ 질문: {question}")
        print(f"{'='*60}\n")

        # 세션 아이디 없으면 새로 발급 (대화 기록용)
        session_id = session_id or str(uuid4())
        # 이전 검색 결과 초기화 (로그 저장용)
        vector_search_instance.last_results = []

        # WandB 세션 시작
        if self.wandb_logger:
            self.wandb_logger.start_session(question)

        # 동기 스트리밍 실행
        for chunk in self._run_stream_sync(question, session_id, start_time):
            yield chunk
