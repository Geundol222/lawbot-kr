import streamlit as st
import time
from backend.src.agent import run_agent

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
        with st.spinner("🔍 법령 검색 중..."):
            try:
                response = run_agent(prompt)
                st.markdown(response)
                
                # 응답 저장
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response
                })
            
            except Exception as e:
                error_msg = f"❌ 오류가 발생했습니다: {str(e)}"
                st.error(error_msg)
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
        - 회사가 야근수당 안 주는데?
        - 월세 계약 해지하고 싶어
        - 교통사고 났는데 보험처리
        - 소 소유권 분쟁 어떡해?
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
    st.caption("**모델:** Google Gemini 2.0 Flash")
    st.caption("**데이터:** 국가법령정보센터 API")
    
    # 통계 (선택사항)
    if st.session_state.messages:
        st.metric("대화 수", len(st.session_state.messages) // 2)