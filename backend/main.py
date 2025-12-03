import uuid
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from src.agent import run_agent
from src.supabase_client import save_conversation, get_stats

app = FastAPI(title='Lawbot-KR API')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

class ChatRequest(BaseModel):
    question: str
    session_id: str = None

class ChatResponse(BaseModel):
    answer: str
    session_id: str

@app.get('/')
def root():
    return {'status': 'ok', 'message': 'Lawbot-KR API'}

@app.get('/health')
def health():
    return {'status': 'healthy'}

@app.get('/stats')
async def stats():
    """통계 조회"""
    return get_stats()

@app.post('/chat')
async def chat(request: ChatRequest):
    """채팅 엔드포인트"""
    session_id = request.session_id or str(uuid.uuid4())
    
    start_time = time.time()
    
    try:
        answer = run_agent(request.question)
        response_time = int((time.time() - start_time) * 1000)
        
        # ⭐ Supabase에 저장 ⭐
        save_conversation(
            session_id=session_id,
            user_question=request.question,
            bot_answer=answer,
            response_time_ms=response_time
        )
        
        return ChatResponse(
            answer=answer,
            session_id=session_id
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))