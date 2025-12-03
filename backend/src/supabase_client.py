import os
from supabase import create_client, Client

from config import SUPABASE_KEY, SUPABASE_URL

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def save_converstion(session_id: str, user_question: str, bot_answer: str,
                     law_name: str=None, article: str=None,
                     response_time_ms: int=None):
    """대화 로그 저장"""
    try:
        session = supabase.table('sessions')\
            .select('*')\
            .eq('session_id', session_id)\
            .execute()

        if not session.data:
            supabase.table('sessions').insert({
                'session_id': session_id
            }).execute()

        supabase.table('conversation_logs').insert({
            'session_id': session_id,
            'uswer_question': user_question,
            'bot_answer': bot_answer,
            'law_name': law_name,
            'article': article,
            'reaponse_time_me': response_time_ms
        }).execute()

        print(f'✅ 대화 저장 완료: {session_id}')

    except Exception as e:
        print(f'⚠️ 대화 저장 실패: {e}')


def get_law_from_cache(law_name: str, article: str):
    """캐시에서 법령 조회"""
    try:
        result = supabase.table('law_cache')\
            .select('*')\
            .eq('law_name', law_name)\
            .eq('article', article)\
            .execute()
        
        if result.data:
            # 히트 카운트 증가
            supabase.rpc("increment_cache_hit", {
                "p_law_name": law_name,
                "p_article": article
            }).execute()
            
            print(f"✅ 캐시 히트: {law_name} {article}")
            return result.data[0]["content"]
        
        return None
    
    except Exception as e:
        print(f"⚠️ 캐시 조회 실패: {e}")
        return None


def save_law_to_cache(law_name: str, article: str, content: str, mst: str = None):
    """법령 캐시에 저장"""
    try:
        supabase.table("law_cache").upsert({
            "law_name": law_name,
            "article": article,
            "content": content,
            "mst": mst
        }).execute()
        
        print(f"✅ 캐시 저장: {law_name} {article}")
    
    except Exception as e:
        print(f"⚠️ 캐시 저장 실패: {e}")


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