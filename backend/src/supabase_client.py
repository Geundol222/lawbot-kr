import os
from supabase import create_client, Client

from src.config import SUPABASE_KEY, SUPABASE_URL

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Supabase 환경변수가 설정되지 않았습니다!")

print(f"✅ Supabase URL: {SUPABASE_URL[:30]}...")
print(f"✅ Supabase KEY: {SUPABASE_KEY[:30]}...")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def save_conversation(session_id: str, user_question: str, bot_answer: str,
                     law_name: str = None, article: str = None,
                     response_time_ms: int = None):
    """대화 로그 저장"""
    try:
        # 세션 확인 또는 생성
        session = supabase.table("sessions")\
            .select("*")\
            .eq("session_id", session_id)\
            .execute()
        
        if not session.data:
            # 새 세션 생성
            supabase.table("sessions").insert({
                "session_id": session_id
            }).execute()
        
        # 대화 로그 저장
        supabase.table("conversation_logs").insert({
            "session_id": session_id,
            "user_question": user_question,
            "bot_answer": bot_answer,
            "law_name": law_name,
            "article": article,
            "response_time_ms": response_time_ms
        }).execute()
        
        print(f"✅ 대화 저장 완료: {session_id}")
    
    except Exception as e:
        print(f"⚠️ 대화 저장 실패: {e}")


def get_stats():
    """통계 조회"""
    try:
        # 총 대화 수
        total = supabase.table("conversation_logs")\
            .select("*", count="exact")\
            .execute()
        
        # 자주 찾는 법령 TOP 5
        popular_laws = supabase.table("law_cache")\
            .select("law_name, article, hit_count")\
            .order("hit_count", desc=True)\
            .limit(5)\
            .execute()
        
        return {
            "total_conversations": total.count,
            "popular_laws": popular_laws.data
        }
    
    except Exception as e:
        print(f"⚠️ 통계 조회 실패: {e}")
        return {}