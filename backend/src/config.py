import os
from dotenv import load_dotenv

# 환경변수는 바로 로드
load_dotenv()

# 법령 API
LAW_API_SERVICE = os.getenv('LAW_API_SERVICE')
LAW_API_SEARCH = os.getenv('LAW_API_SEARCH')
LAW_API_OC = os.getenv('LAW_API_OC')

# Google
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY')

LAW_KEY = {
    '시행일 본문': 'eflaw',
    '공표일 본문': 'law',
    '법령 연혁 본문': 'lsHistory',
    '행정규칙 본문': 'admrul',
    '판례 본문': 'prec',
    '행정심판례 본문': 'decc',
    '법령용어': 'lstrmAI',
    '일상용어': 'dlytrm',
    '관련법령': 'lsRlt',
    '법령-일상': 'lstrmRlt',
    '일상-법령': 'dlytrmRlt'
}

# LLM은 함수로 감싸기 (필요할 때만 초기화)
_llm_instance = None

def get_llm():
    """LLM 인스턴스 가져오기 (싱글톤 패턴)"""
    global _llm_instance
    
    if _llm_instance is None:
        from langchain_google_genai import ChatGoogleGenerativeAI
        _llm_instance = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            temperature=0.0
        )
    
    return _llm_instance