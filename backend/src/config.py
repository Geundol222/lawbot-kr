import os
from dotenv import load_dotenv

# 환경변수는 바로 로드 (로컬 개발용, .env 파일이 없으면 무시)
load_dotenv()

# 법령 API
LAW_API_SERVICE = os.getenv('LAW_API_SERVICE')
LAW_API_SEARCH = os.getenv('LAW_API_SEARCH')
LAW_API_OC = os.getenv('LAW_API_OC')

# Google
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Supabase (필수 환경변수)
SUPABASE_URL = os.getenv('SUPABASE_URL')
# 서버 사이드 쓰기 권한을 위해 서비스 롤 키가 있으면 우선 사용하고, 없으면 anon 키로 폴백
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY or os.getenv('SUPABASE_ANON_KEY')

# 필수 환경변수 검증
def validate_required_env_vars():
    """필수 환경변수가 설정되었는지 확인"""
    required_vars = {
        'SUPABASE_URL': SUPABASE_URL,
        'SUPABASE_ANON_KEY': SUPABASE_KEY,
        'GOOGLE_API_KEY': GOOGLE_API_KEY,
    }

    missing_vars = [var_name for var_name, var_value in required_vars.items() if not var_value]

    if missing_vars:
        error_msg = f"❌ 필수 환경변수가 설정되지 않았습니다: {', '.join(missing_vars)}"
        print(error_msg)
        print("\n💡 Hugging Face Spaces에서:")
        print("   Settings → Variables → Add variable에서 환경변수를 설정하세요.")
        print("\n💡 로컬 개발 환경에서:")
        print("   .env 파일을 생성하고 환경변수를 설정하세요.")
        raise ValueError(error_msg)

    print("✅ 환경변수 로드 완료:")
    print(f"   - SUPABASE_URL: {'설정됨' if SUPABASE_URL else '없음'}")
    print(f"   - SUPABASE_ANON_KEY: {'설정됨' if SUPABASE_KEY else '없음'}")
    print(f"   - GOOGLE_API_KEY: {'설정됨' if GOOGLE_API_KEY else '없음'}")
    print(f"   - LAW_API_OC: {'설정됨' if LAW_API_OC else '없음'}")

# 모듈 로드 시 환경변수 검증
validate_required_env_vars()

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

# LLM 인스턴스 캐시 (싱글톤 패턴)
_llm_instances = {}

def get_llm(use_case: str = "generation"):
    """
    용도별 LLM 인스턴스 가져오기 (싱글톤 패턴)

    Args:
        use_case:
            - "generation": 답변 생성 (Gemini 2.5 Flash - 빠르고 저렴)
            - "tool_calling": Function calling, 복잡한 추론 (Gemini 2.0 Flash Thinking - 정확)
            - "judge_exception": 예외 조항 탐지 (Gemini 2.5 Flash Lite - 초고속/초저가)
    """
    global _llm_instances

    if use_case not in _llm_instances:
        from langchain_google_genai import ChatGoogleGenerativeAI

        if use_case == "tool_calling":
            # Function calling과 복잡한 추론은 Thinking 모델
            _llm_instances[use_case] = ChatGoogleGenerativeAI(
                model='gemini-3-pro-preview',
                temperature=0.0
            )
        elif use_case == "generation":
            # 답변 생성은 빠른 Flash
            _llm_instances[use_case] = ChatGoogleGenerativeAI(
                model='gemini-2.5-flash',
                temperature=0.0
            )
        elif use_case == "judge_exception":
            # 예외 조항, 적용 범위 탐지는 초경량 Flash Lite
            _llm_instances[use_case] = ChatGoogleGenerativeAI(
                model='gemini-2.5-flash-lite',
                temperature=0.0
            )

    return _llm_instances[use_case]
