# app.py
import streamlit as st
import time
import sys
from pathlib import Path
from uuid import uuid4

# Python 출력 버퍼링 비활성화 (로그 즉시 출력)
import os
os.environ['PYTHONUNBUFFERED'] = '1'

# backend 경로 추가
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

from src.agentic_rag import AgenticRAG, preload_embedding_model
from src.embeddings.bm25_search import preload_bm25_index

# 임베딩 모델 미리 로드 (앱 시작 시 한 번만)
preload_embedding_model()
# BM25 인덱스 미리 빌드 (백그라운드)
preload_bm25_index(background=True)

# 페이지 설정
st.set_page_config(
    page_title="⚖️ 한국 법령 챗봇",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 타이틀
st.title("⚖️ 한국 법령 챗봇")
st.caption("💬 법률 질문을 입력하세요. 구체적인 조문이나 상황을 설명해주세요.")

# 세션 상태 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# Supabase용 세션 ID (대화별 유지)
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid4())

# AgenticRAG 인스턴스 초기화 (세션마다 한 번만)
if "agent" not in st.session_state:
    st.session_state.agent = AgenticRAG(
        session_id=st.session_state.session_id,  # ← 세션 ID 전달
        use_memory=True  # ← Buffer Memory 활성화
    )

# 이전 대화 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력
if prompt := st.chat_input("예: 민법 제750조 알려줘"):
    # 사용자 메시지 추가
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # 챗봇 응답
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        status_placeholder = st.empty()

        try:
            # 스트리밍 답변 생성
            full_response = ""
            current_status = "🔍 준비 중..."
            import json

            for chunk in st.session_state.agent.run_stream(
                prompt,
                session_id=st.session_state.session_id
            ):
                # SSE 이벤트 파싱 시도
                if chunk.startswith("data: "):
                    try:
                        event_data = json.loads(chunk[6:])
                        event_type = event_data.get("type")

                        if event_type == "searching":
                            current_status = "📚 법령을 검색 중입니다..."
                            status_placeholder.info(current_status)

                        elif event_type == "checking_exceptions":
                            articles = event_data.get("articles", [])
                            current_status = f"💭 예외 조항을 검색중입니다...\n\n확인할 조문: {', '.join(articles)}"
                            status_placeholder.warning(current_status)

                        elif event_type == "answer_start":
                            status_placeholder.empty()  # 상태 메시지 제거
                            current_status = ""

                        elif event_type == "answer_chunk":
                            text = event_data.get("text", "")
                            full_response += text
                            message_placeholder.markdown(full_response + "▌")

                        elif event_type == "error":
                            error_msg = event_data.get("message", "Unknown error")
                            status_placeholder.error(f"❌ {error_msg}")

                    except json.JSONDecodeError:
                        # JSON이 아니면 일반 텍스트로 처리 (하위 호환)
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")
                else:
                    # SSE 형식이 아니면 일반 텍스트
                    full_response += chunk
                    message_placeholder.markdown(full_response + "▌")

            # 커서 제거하고 최종 답변 표시
            status_placeholder.empty()
            message_placeholder.markdown(full_response)

            # 응답 저장
            st.session_state.messages.append({
                "role": "assistant",
                "content": full_response
            })

        except Exception as e:
            import traceback
            error_msg = f"❌ 오류가 발생했습니다: {str(e)}\n\n{traceback.format_exc()}"
            message_placeholder.error(error_msg)
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_msg
            })

# 사이드바
with st.sidebar:
    st.header("📚 사용 가이드")
    
    st.subheader("💬 질문 예시")
    
    with st.expander("📜 구체적 조문 질문"):
        st.markdown("""
        - 헌법 제1조 1항이 뭐야?
        - 민법 제750조 알려줘
        - 근로기준법 제56조 내용
        - 형법 제250조는?
        """)
    
    with st.expander("🤔 상황 설명 질문"):
        st.markdown("""
        - 야근수당은 얼마나 받을 수 있어?
        - 회사가 야근수당 안 주는데?
        - 월세 계약 해지하고 싶어
        - 교통사고 났는데 보험처리
        """)
    
    st.divider()
    
    st.subheader("⚙️ 설정")
    
    if st.button("🗑️ 대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    
    st.subheader("⚠️ 주의사항")
    st.caption("본 챗봇은 법률 정보 제공 목적이며, 정식 법률 자문이 아닙니다.")
    
    st.divider()
    
    st.subheader("ℹ️ 정보")
    st.caption("**모델:** Google Gemini 2.5 Flash")
    st.caption("**벡터 DB:** Supabase (조 단위 임베딩)")
    st.caption("**데이터:** 국가법령정보센터 API")

    st.divider()

    st.subheader("🔍 작동 방식")
    st.caption("""
    1. 벡터 검색으로 관련 법령 찾기
    2. 유사도 ≥ 0.7: 조문 상세 조회
    3. 유사도 < 0.7: API로 직접 검색
    4. LLM이 법령 기반 답변 생성
    """)
    
    # 통계
    if st.session_state.messages:
        st.metric("대화 수", len(st.session_state.messages) // 2)
