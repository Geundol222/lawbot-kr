# app.py
import streamlit as st
import time
import sys
from pathlib import Path

# backend 경로 추가
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

from src.agentic_rag import AgenticRAG

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

# AgenticRAG 인스턴스 초기화 (세션마다 한 번만)
if "agent" not in st.session_state:
    st.session_state.agent = AgenticRAG()

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

        with st.spinner("🔍 벡터 DB 검색 중..."):
            try:
                # AgenticRAG로 답변 생성
                response = st.session_state.agent.run(prompt)

                # 타이핑 효과 (선택사항)
                message_placeholder.markdown(response)

                # 응답 저장
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response
                })

            except Exception as e:
                error_msg = f"❌ 오류가 발생했습니다: {str(e)}"
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
    st.caption("**벡터 DB:** Supabase (3,926개 조문)")
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