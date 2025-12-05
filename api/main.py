"""
FastAPI 엔드포인트 (Vercel/Render 배포용)
"""
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

# backend 경로 추가
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from src.agentic_rag import AgenticRAG

# FastAPI 앱
app = FastAPI(
    title="Lawbot-KR API",
    description="한국 법령 상담 AI - Agentic RAG",
    version="2.0.0"
)

# CORS 설정 (Vercel 프론트엔드에서 접근 가능하도록)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Agent 인스턴스 (싱글톤)
agent = None

def get_agent():
    """Agent 인스턴스 가져오기 (Lazy Loading)"""
    global agent
    if agent is None:
        print("🤖 AgenticRAG 초기화 중...")
        agent = AgenticRAG()
        print("✅ AgenticRAG 초기화 완료")
    return agent

# Request/Response 모델
class ChatRequest(BaseModel):
    question: str
    session_id: str = None

class ChatResponse(BaseModel):
    answer: str
    session_id: str

# 엔드포인트
@app.get("/")
def root():
    """Health check"""
    return {
        "status": "ok",
        "service": "Lawbot-KR API",
        "version": "2.0.0"
    }

@app.get("/health")
def health():
    """상태 확인"""
    return {"status": "healthy"}

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    채팅 엔드포인트

    Args:
        request: ChatRequest
            - question: 사용자 질문
            - session_id: 세션 ID (선택)

    Returns:
        ChatResponse
            - answer: AI 답변
            - session_id: 세션 ID
    """
    session_id = request.session_id or str(uuid.uuid4())

    try:
        # Agent 실행
        agent_instance = get_agent()
        answer = agent_instance.run(request.question)

        return ChatResponse(
            answer=answer,
            session_id=session_id
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing question: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
