"""
FastAPI 엔드포인트 (Vercel/Render 배포용)
"""
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uuid
import time
import json

# backend 경로 추가
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from src.agentic_rag import AgenticRAG, preload_embedding_model
from src.monitoring import get_wandb_logger, FastAPILogger

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

# WandB 로거 초기화
try:
    fastapi_logger = FastAPILogger(get_wandb_logger())
except Exception:
    fastapi_logger = None

def get_agent():
    """Agent 인스턴스 가져오기 (Lazy Loading)"""
    global agent
    if agent is None:
        print("🤖 AgenticRAG 초기화 중...")
        agent = AgenticRAG()
        print("✅ AgenticRAG 초기화 완료")
    return agent

# 앱 시작 시 임베딩 모델 미리 로드
@app.on_event("startup")
async def startup_event():
    """FastAPI 앱 시작 시 실행"""
    print("🚀 FastAPI 앱 시작 - 임베딩 모델 로딩 시작...")
    preload_embedding_model()
    print("✅ 임베딩 모델 로딩 완료!")

    # BM25 인덱스 preload
    print("🔍 BM25 인덱스 로딩 시작...")
    from src.embeddings.bm25_search import preload_bm25_index
    preload_bm25_index(background=False)
    print("✅ BM25 인덱스 로딩 완료!")

# Request/Response 모델
class ChatRequest(BaseModel):
    question: str
    session_id: str = None

class ChatResponse(BaseModel):
    answer: str
    session_id: str

class FeedbackRequest(BaseModel):
    session_id: str
    message_index: int
    feedback_type: str  # 'positive' or 'negative'
    message_content: str

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
async def chat(request: ChatRequest, http_request: Request, http_response: Response):
    """
    채팅 엔드포인트 (Non-streaming)

    Args:
        request: ChatRequest
            - question: 사용자 질문
            - session_id: 세션 ID (선택)

    Returns:
        ChatResponse
            - answer: AI 답변
            - session_id: 세션 ID
    """
    # 기기 단위 식별자: 쿠키에 없으면 새로 생성
    def ensure_device_id(req: Request, res: Response) -> str:
        existing = req.cookies.get("device_id")
        if existing:
            return existing
        new_id = str(uuid.uuid4())
        # 2년 보관, Lax로 CSRF 위험 낮춤, HttpOnly는 JS에서 접근이 필요하면 False 유지
        res.set_cookie(
            key="device_id",
            value=new_id,
            max_age=60 * 60 * 24 * 365 * 2,
            samesite="lax",
        )
        return new_id

    device_id = ensure_device_id(http_request, http_response)
    session_id = request.session_id or device_id
    start_time = time.time()

    error_message = None
    answer = ""
    status_code = 200

    try:
        # Agent 실행
        agent_instance = get_agent()
        answer = agent_instance.run(request.question, session_id=session_id)

        # WandB 로깅
        if fastapi_logger:
            response_time = time.time() - start_time
            fastapi_logger.log_request(
                session_id=session_id,
                question=request.question,
                answer_length=len(answer),
                response_time=response_time,
                status_code=status_code,
                error_message=None
            )

        return ChatResponse(
            answer=answer,
            session_id=session_id
        )

    except Exception as e:
        error_message = str(e)
        status_code = 500

        # WandB 로깅 (에러)
        if fastapi_logger:
            response_time = time.time() - start_time
            fastapi_logger.log_request(
                session_id=session_id,
                question=request.question,
                answer_length=0,
                response_time=response_time,
                status_code=status_code,
                error_message=error_message
            )

        raise HTTPException(
            status_code=status_code,
            detail=f"Error processing question: {error_message}"
        )


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest, http_request: Request, http_response: Response):
    """
    채팅 엔드포인트 (Streaming)

    Args:
        request: ChatRequest
            - question: 사용자 질문
            - session_id: 세션 ID (선택)

    Returns:
        StreamingResponse (Server-Sent Events)
            - data: {"chunk": "텍스트", "done": false}
            - data: {"done": true, "session_id": "..."}
    """
    # 기기 단위 식별자
    def ensure_device_id(req: Request, res: Response) -> str:
        existing = req.cookies.get("device_id")
        if existing:
            return existing
        new_id = str(uuid.uuid4())
        res.set_cookie(
            key="device_id",
            value=new_id,
            max_age=60 * 60 * 24 * 365 * 2,
            samesite="lax",
        )
        return new_id

    device_id = ensure_device_id(http_request, http_response)
    session_id = request.session_id or device_id

    async def event_generator():
        """SSE 이벤트 생성"""
        try:
            agent_instance = get_agent()

            # 스트리밍 시작
            for chunk in agent_instance.run_stream(request.question, session_id=session_id):
                # SSE 형식으로 전송
                yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"

            # 완료 신호
            yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"

        except Exception as e:
            # 에러 전송
            error_data = {
                'error': str(e),
                'done': True
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx 버퍼링 비활성화
        }
    )


@app.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    """
    사용자 피드백 저장

    Args:
        request: FeedbackRequest
            - session_id: 세션 ID
            - message_index: 메시지 인덱스
            - feedback_type: 'positive' or 'negative'
            - message_content: 메시지 내용

    Returns:
        {"success": True}
    """
    try:
        from src.supabase_client import supabase

        # Supabase에 피드백 저장
        feedback_data = {
            "session_id": request.session_id,
            "message_index": request.message_index,
            "feedback_type": request.feedback_type,
            "message_content": request.message_content,
        }

        result = supabase.table("user_feedback").insert(feedback_data).execute()

        return {"success": True, "id": result.data[0]["id"] if result.data else None}

    except Exception as e:
        print(f"⚠️ 피드백 저장 실패: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save feedback: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
