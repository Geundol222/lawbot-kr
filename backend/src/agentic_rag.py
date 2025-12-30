"""
Agentic RAG 시스템
- 도구 정의
- 그래프 구성
- 실행 인터페이스
"""

from typing import Optional
import requests
from langgraph.graph import StateGraph, END
from langchain.tools import tool

from src.embeddings.vector_search import VectorSearch
from src.law_api import (
    search_law_list,
    get_law_article,
    get_law_detail,
    format_jo_number,
    extract_article_content,
    fetch_byeol
)
from src.config import get_llm, llm_invoke_with_retry, LAW_API_SEARCH, LAW_API_SERVICE, LAW_API_OC
from src.monitoring import get_wandb_logger, AgenticRAGLogger
from src.agent_state import AgentState
from src.agent_nodes import AgentNodes
from src.agent_streaming import AgentStreaming


# ========================================
# 임베딩 모델 싱글톤 - 앱 시작 시 미리 로드
# ========================================

_embedding_model_instance = None
_embedding_model_loading = False  # 로딩 중 플래그 (Thread-safe)

def _get_embedding_model():
    """임베딩 모델 싱글톤 (한 번만 로드)"""
    global _embedding_model_instance, _embedding_model_loading

    if _embedding_model_instance is None:
        # 다른 스레드가 로딩 중이면 기다림
        import time
        while _embedding_model_loading:
            time.sleep(0.1)

        # 다시 확인 (다른 스레드가 로드 완료했을 수 있음)
        if _embedding_model_instance is None:
            _embedding_model_loading = True
            try:
                from sentence_transformers import SentenceTransformer
                print("[INFO] 임베딩 모델 로드 중... (최초 1회만)")
                _embedding_model_instance = SentenceTransformer('intfloat/multilingual-e5-large-instruct')
                print("[OK] 임베딩 모델 로드 완료!")
            finally:
                _embedding_model_loading = False

    return _embedding_model_instance

def preload_embedding_model():
    """앱 시작 시 임베딩 모델 미리 로드 (백그라운드)"""
    import threading

    def load_in_background():
        _get_embedding_model()

    # 백그라운드 스레드로 로드 (앱 시작을 블로킹하지 않음)
    thread = threading.Thread(target=load_in_background, daemon=True)
    thread.start()
    print("[INFO] 임베딩 모델 백그라운드 로딩 시작...")


# ========================================
# Tools 정의
# ========================================

vector_search_instance = VectorSearch()

@tool
def search_vector_db(query: str) -> str:
    """
    벡터 데이터베이스에서 유사한 법령 검색 (첫 번째 단계)

    임베딩된 조문에서 빠르게 검색하고 조문 내용을 바로 반환합니다.
    이 도구를 먼저 호출하여 벡터 DB에 관련 법령이 있는지 확인하세요.

    Args:
        query: 검색할 질문

    Returns:
        - 성공: 법령명, 조문, 유사도, 조문 내용 포함 → 바로 답변 작성!
        - 실패: VECTOR_DB_NO_MATCH → search_law_by_api 사용

    중요: 이 도구가 성공하면 조문 내용이 포함되므로 추가 도구 호출 불필요!
    """
    # 1차 검색: 원본 쿼리
    results = vector_search_instance.search(query, top_k=5, threshold=0.7)

    # 1차 실패 시: Query Expansion (핵심 법률 용어만 추출해서 재검색)
    if not results:
        # flash-lite로 빠르게 핵심 법률 용어만 추출
        lite_llm = get_llm("flash-lite")
        expansion_prompt = f"""질문에서 핵심 법률 용어만 추출하세요

질문: {query}

규칙:
- 15자 이내

핵심 용어:"""

        try:
            response = llm_invoke_with_retry(lite_llm, expansion_prompt)
            core_term = ""
            if hasattr(response, 'content'):
                content = response.content
                if isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and 'text' in part:
                            core_term += part['text']
                elif isinstance(content, str):
                    core_term = content

            core_term = core_term.strip()

            # 추출된 핵심 용어가 원본과 다르면 재검색
            if core_term and len(core_term) > 2 and core_term != query:
                print(f"🔍 Query Expansion: '{query}' → '{core_term}'")
                results = vector_search_instance.search(core_term, top_k=5, threshold=0.7)
        except Exception as e:
            print(f"⚠️ Query Expansion 실패: {e}")

    if not results:
        # 유사도 0.7 이상인 결과가 없음
        return "VECTOR_DB_NO_MATCH: 벡터 DB에서 유사도 0.7 이상인 법령을 찾지 못했습니다. search_law_by_api를 사용하여 직접 검색하세요."

    # 판례 요지 조회 헬퍼
    def fetch_prec_summaries(law_name: str, article: str, limit: int = 3) -> list[str]:
        summaries = []

        def _flatten(val):
            if val is None:
                return ""
            if isinstance(val, str):
                return val
            if isinstance(val, list):
                return " ".join(_flatten(v) for v in val if v is not None)
            if isinstance(val, dict):
                return " ".join(_flatten(v) for v in val.values() if v is not None)
            return str(val)

        params = {
            "OC": LAW_API_OC,
            "target": "prec",
            "type": "JSON",
            "JO": f"{law_name} {article}",
            "display": 20,
            "page": 1,
            "search": 2,  # 본문 검색
        }
        try:
            resp = requests.get(LAW_API_SEARCH, params=params, timeout=10)
            data = resp.json() if resp.text else {}
            precs = data.get("PrecSearch", {}).get("prec", [])
            if isinstance(precs, dict):
                precs = [precs]
        except Exception as e:
            print(f"[WARN] 판례 목록 조회 실패: {e}")
            precs = []

        if not precs:
            return summaries

        for prec in precs[:limit]:
            pid = prec.get("판례일련번호")
            case_name = prec.get("사건명") or prec.get("판례명") or ""
            case_no = prec.get("사건번호", "")
            court = prec.get("법원명", "")
            date = prec.get("선고일자", "")
            if not pid:
                continue

            try:
                d_resp = requests.get(
                    LAW_API_SERVICE,
                    params={"OC": LAW_API_OC, "target": "prec", "type": "JSON", "ID": pid},
                    timeout=10,
                )
                d_json = d_resp.json() if d_resp.text else {}
                prec_root = d_json.get("prec", {})
                content = prec_root.get("판례내용", {})
                summary = _flatten(content.get("판결요지", "")).replace("<br/>", " ").replace("<br>", " ").strip()
                refs = _flatten(content.get("참조조문", "")).replace("<br/>", " ").replace("<br>", " ").strip()
            except Exception as e:
                summary = f"(판례 상세 조회 실패: {e})"
                refs = ""

            summaries.append(
                f"- [{court} {case_no} ({date})] {case_name}\n  요지: {summary or '요약 없음'}\n  참조조문: {refs or 'N/A'}"
            )

        return summaries

    # 결과를 구조화된 형식으로 반환 (조문 내용 포함)
    print(f"✅ 벡터 검색 성공: {len(results)}개 조문 발견")
    for r in results[:5]:
        print(f"  - {r['law_name']} {r['article']} (유사도: {r['similarity']:.2f})")

    result_text = "=== 벡터 검색 결과 (유사도 0.7 이상) ===\n\n"
    for idx, r in enumerate(results[:5], 1):  # 상위 5개로 증가
        result_text += f"[결과 {idx}]\n"
        result_text += f"법령: {r['law_name']}\n"
        result_text += f"조문: {r['article']}\n"
        result_text += f"유사도: {r['similarity']:.2f}\n"
        result_text += f"내용: {r.get('content', '내용 없음')}\n"

        precs = fetch_prec_summaries(r['law_name'], r['article'], limit=3)
        if precs:
            print(f"[DEBUG] 판례 요지 {len(precs)}건 조회: {r['law_name']} {r['article']}")
            result_text += "관련 판례 요지:\n" + "\n".join(precs) + "\n"
        else:
            print(f"[DEBUG] 판례 요지 없음: {r['law_name']} {r['article']}")

        result_text += "\n"

    result_text += "\n✅ 위 조문 내용으로 답변을 작성하세요. 추가 도구 호출 불필요.\n"
    result_text += "필요시 check_exceptions_needed로 예외 조항을 확인하세요!"

    return result_text


@tool
def get_full_article_content(law_name: str, article: str, mst: str) -> str:
    """
    법령의 특정 조문 전체 내용 가져오기

    벡터 검색으로 찾은 법령의 전체 내용을 API로 조회

    Args:
        law_name: 법령명
        article: 조문 (예: "제56조")
        mst: 법령일련번호

    Returns:
        조문 전체 내용
    """
    if not mst:
        return "MST(법령일련번호) 정보가 없어 조문을 가져올 수 없습니다. search_law_by_api를 사용하세요."

    # 조 단위 청킹이므로 _part suffix 제거 불필요
    jo_formatted = format_jo_number(article)
    law_data = get_law_article(mst=mst, jo=jo_formatted)
    content = extract_article_content(law_data)

    if content and "오류" not in content:
        return f"=== {law_name} {article} ===\n\n{content}"
    else:
        return f"조문 가져오기 실패: {content}"


@tool
def check_exceptions_needed(law_content: str, user_question: str) -> str:
    """
    법령 내용에서 예외조항이나 적용범위 확인이 필요한지 판단

    gemini-2.5-flash-lite 모델을 사용하여 빠르게 분석합니다.

    Args:
        law_content: 검색된 법령 내용
        user_question: 사용자 질문

    Returns:
        JSON 문자열: {"needed": true/false, "articles_to_search": ["법령명 조문번호"], "reason": "이유"}
    """
    import json

    # 입력 길이 제한 (더 짧게 - 빠른 응답 위해)
    max_content_length = 1500  # 약 750 토큰
    if len(law_content) > max_content_length:
        law_content = law_content[:max_content_length] + "\n\n(... 내용 생략 ...)"

    # gemini-2.5-flash-lite 모델 사용
    lite_llm = get_llm("flash-lite")

    prompt = f"""사용자 질문에 대해 추가 법령 검색이 필요한지 판단하세요.

사용자 질문: {user_question}

찾은 법령:
{law_content}

판단 기준:
1. 사용자 질문의 조건 (예: "5인 미만", "10년 이상")이 법령 내용에 없음
   → 해당 조건의 적용 범위를 규정하는 조문 필요 (예: 근로기준법 제11조)

2. 법령이 다른 조문을 명시적으로 참조 (예: "제X조에 따른", "제Y조 준용")
   → 참조된 조문 필요

3. 예외/단서 조항 명시 (예: "단, ~인 경우 제외", "다만 제Z조는 예외")
   → 해당 예외 조문 필요

**중요:** 이미 찾은 조문을 다시 검색하지 마세요!
- 법령 내용이나 질문에 "별표"/"별지"/"서식"이 나오면 byeol_to_search에 "법령명 별표 번호"를 넣어 별표 검색이 필요함을 표시하세요.

응답 (JSON):
{{
  "needed": True/False,
  "articles_to_search": ["법령명 조문번호"],
  "byeol_to_search": ["법령명 별표번호"],
  "reason": "이유"
}}

예시 1 (적용 범위):
질문: "5인 미만 사업장 해고 예고수당"
법령: 근로기준법 제26조 (해고 예고)
→ {{"needed": True, "articles_to_search": ["근로기준법 제11조"], "reason": "5인 미만 사업장 적용 범위는 제11조에 규정"}}

예시 2 (참조):
법령: "제762조를 준용한다"
→ {{"needed": True, "articles_to_search": ["민법 제762조"], "reason": "제762조 참조"}}

예시 3 (불필요):
질문: "해고 예고수당은?"
법령: 근로기준법 제26조 (완전한 답변)
→ {{"needed": False, "articles_to_search": [], "reason": "충분"}}

예시 4 (시행령):
질문: "대통령령에 의해"
법령: 근로기준법 시행령
→ {{"needed": True, "articles_to_search": [], "reason": "대통령령=시행령 확인 (조문번호 불명확)"}}

예시 5 (별표):
질문: "근로기준법 별표 1에서 정한 업종?"
법령: 근로기준법
→ {{"needed": True, "articles_to_search": [], "byeol_to_search": ["근로기준법 별표 1"], "reason": "질문에서 별표 1을 직접 언급"}}
"""

    try:
        response = llm_invoke_with_retry(lite_llm, prompt)

        # 응답 텍스트 추출
        response_text = ""
        if hasattr(response, 'content'):
            content = response.content
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and 'text' in part:
                        response_text += part['text']
            elif isinstance(content, str):
                response_text = content
        else:
            response_text = str(response)

        # JSON 파싱 시도
        # LLM이 마크다운으로 감싼 경우 제거
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()

        result = json.loads(response_text)

        return json.dumps(result, ensure_ascii=False)

    except Exception as e:
        # 오류 시 안전하게 필요 없음으로 반환
        return json.dumps({
            "needed": False,
            "articles_to_search": [],
            "byeol_to_search": [],
            "reason": f"분석 중 오류 발생: {str(e)}"
        }, ensure_ascii=False)


@tool
def search_byeol(law_name: str, byeol_no: str = "1", mst: str = "") -> str:
    """
    별표/별지/서식 본문 조회 (법령명 + 별표 번호)

    Args:
        law_name: 법령명 (예: "근로기준법")
        byeol_no: 별표 번호 (예: "1", "1의2")
        mst: (선택) 법령일련번호. 비우면 자동 조회.

    Returns:
        HTML 프리뷰, 조회 URL, JSON 발췌를 포함한 문자열
    """
    return fetch_byeol(law_name=law_name, mst=mst, byeol_no=byeol_no, fmt="HTML")


@tool
def search_prec_by_article(law_name: str, article: str) -> str:
    """
    특정 법령/조문을 참조한 판례의 판결요지 조회 (실시간 API)

    Args:
        law_name: 법령명 (예: "근로기준법")
        article: 조문 (예: "제26조")

    Returns:
        상위 3~5개 판례의 요약 리스트
    """
    import requests

    def _flatten(val):
        if val is None:
            return ""
        if isinstance(val, str):
            return val
        if isinstance(val, list):
            return " ".join(_flatten(v) for v in val if v is not None)
        if isinstance(val, dict):
            return " ".join(_flatten(v) for v in val.values() if v is not None)
        return str(val)

    # 1) 판례 목록 (본문 검색)
    params = {
        "OC": LAW_API_OC,
        "target": "prec",
        "type": "JSON",
        "JO": f"{law_name} {article}",
        "display": 20,
        "page": 1,
        "search": 2,  # 본문 검색
    }
    try:
        resp = requests.get(LAW_API_SEARCH, params=params, timeout=15)
        data = resp.json() if resp.text else {}
        precs = data.get("PrecSearch", {}).get("prec", [])
        if isinstance(precs, dict):
            precs = [precs]
    except Exception as e:
        return f"판례 목록 조회 실패: {e}"

    if not precs:
        return f"{law_name} {article}를 참조한 판례를 찾지 못했습니다."

    results = []
    for prec in precs[:5]:
        prec_id = prec.get("판례일련번호")
        case_name = prec.get("사건명") or prec.get("판례명") or ""
        case_no = prec.get("사건번호", "")
        court = prec.get("법원명", "")
        date = prec.get("선고일자", "")
        if not prec_id:
            continue

        # 2) 판례 상세
        detail_params = {
            "OC": LAW_API_OC,
            "target": "prec",
            "type": "JSON",
            "ID": prec_id,
        }
        try:
            d_resp = requests.get(LAW_API_SERVICE, params=detail_params, timeout=15)
            d_json = d_resp.json() if d_resp.text else {}
            prec_root = d_json.get("prec", {})
            content = prec_root.get("판례내용", {})
            summary = _flatten(content.get("판결요지", "")).replace("<br/>", " ").replace("<br>", " ").strip()
            refs = _flatten(content.get("참조조문", "")).replace("<br/>", " ").replace("<br>", " ").strip()
        except Exception as e:
            summary = f"(판례 상세 조회 실패: {e})"
            refs = ""

        results.append(
            f"- [{court} {case_no} ({date})] {case_name}\n  요지: {summary or '요약 없음'}\n  참조조문: {refs or 'N/A'}"
        )

    if not results:
        return f"{law_name} {article}를 참조한 판례를 찾지 못했습니다."

    return "=== 관련 판례 요지 ===\n" + "\n\n".join(results)


@tool
def search_law_by_api(law_name: str, query: str = "", article_number: str = None) -> str:
    """
    API로 법령 검색 후 semantic search로 관련 조문 추출

    전체 법령을 가져온 후, 사용자 질문과 가장 관련성 높은 조문만 반환합니다.
    search_vector_db에서 VECTOR_DB_NO_MATCH가 반환된 경우에만 사용하세요.

    Args:
        law_name: 검색할 법령명 (예: "근로기준법", "민법", "병역법")
        query: 사용자 질문 (semantic search에 사용, 특정 조문만 원하면 빈 문자열 가능)
        article_number: 선택적 조문 번호 (특정 조문을 원하면 지정)

    Returns:
        질문과 관련성 높은 상위 3-5개 조문
    """
    # 벡터 검색이 이미 성공한 경우 불필요한 API 호출 방지
    if vector_search_instance.last_results:
        return "SKIP_API: 벡터 검색 결과가 이미 있어 API 호출을 건너뜁니다."

    # 법령 검색
    search_result = search_law_list(law_name)

    if "error" in search_result:
        return f"법령 검색 실패: {search_result['error']}"

    law_list = search_result.get("LawSearch", {}).get("law", [])

    if isinstance(law_list, dict):
        law_list = [law_list]

    if not law_list:
        return f"'{law_name}' 관련 법령을 찾을 수 없습니다. 법령명을 정확하게 입력해주세요."

    # 가장 관련성 높은 법령 찾기 (이름이 가장 짧은 것 = 기본법)
    law_list.sort(key=lambda x: len(x.get("법령명한글", "")))
    law = law_list[0]
    law_title = law.get("법령명한글")
    mst = law.get("법령일련번호")

    if not mst:
        return "법령일련번호를 찾을 수 없습니다."

    # 특정 조문 검색인지 전체 검색인지 판단
    if article_number:
        # 특정 조문만 가져오기
        jo_formatted = format_jo_number(article_number)
        law_data = get_law_article(mst=mst, jo=jo_formatted)
        content = extract_article_content(law_data)

        if content and "오류" not in content:
            return f"=== {law_title} {article_number} ===\n\n{content}"
        else:
            return f"조문 가져오기 실패: {content}"
    else:
        # 전체 본문 가져오기 → Semantic search로 관련 조문만 추출
        law_data = get_law_detail(mst)
        content = extract_article_content(law_data)

        if "오류" in content:
            return f"법령 내용 가져오기 실패: {content}"

        # 조문별로 분리 (각 조문은 "제X조"로 시작)
        import re
        articles = re.split(r'\n\n(?=제\d+조)', content)

        if len(articles) <= 5:
            # 조문이 5개 이하면 전부 반환
            return f"=== {law_title} ===\n\n{content[:3000]}\n\n... (총 {len(articles)}개 조문)"

        # Semantic search: 질문과 각 조문의 유사도 계산
        try:
            import numpy as np

            # 임베딩 모델 (기존 사용 모델 재사용 - 싱글톤)
            model = _get_embedding_model()

            # 질문 임베딩
            query_embedding = model.encode(query, convert_to_numpy=True)

            # 각 조문 임베딩
            article_embeddings = model.encode(articles, convert_to_numpy=True)

            # 코사인 유사도 계산
            similarities = np.dot(article_embeddings, query_embedding) / (
                np.linalg.norm(article_embeddings, axis=1) * np.linalg.norm(query_embedding)
            )

            # 상위 5개 조문 선택
            top_indices = np.argsort(similarities)[-5:][::-1]

            # 결과 조합
            result_articles = [articles[i] for i in top_indices]
            result_text = "\n\n".join(result_articles)

            return f"=== {law_title} (질문과 가장 관련성 높은 조문) ===\n\n{result_text}"

        except Exception as e:
            # Semantic search 실패 시 앞부분만 반환
            print(f"⚠️ Semantic search 실패: {e}, 앞부분만 반환합니다.")
            return f"=== {law_title} ===\n\n{content[:3000]}\n\n... (이하 생략)"


# ========================================
# Agent 정의
# ========================================

class AgenticRAG:
    def __init__(self, session_id: Optional[str] = None, mode: str = "current"):
        """
        AgenticRAG 초기화

        Args:
            session_id: 세션 ID (프론트엔드에서 전달, WandB 로깅용)
            mode: 평가 모드 ("vanilla", "current", "self_rag")
                - vanilla: 벡터 검색 1회만, 예외 조항 체크 X
                - current: 현재 시스템 (예외 조항 체크)
                - self_rag: Self-RAG (검색 → 평가 → 재검색)
        """
        self.session_id = session_id
        self.mode = mode

        # 단일 LLM 사용 (Gemini 2.5 Flash)
        self.llm = get_llm("flash")

        # ⭐ Tools 바인딩 ⭐
        # 외부 노출(테스트) 기준 3개, 내부용 check_exceptions_needed는 별도 바인딩
        self.tools = [
            search_vector_db,
            get_full_article_content,
            search_byeol,
            search_law_by_api,
            search_prec_by_article,
        ]
        self.llm_with_tools = self.llm.bind_tools(self.tools + [check_exceptions_needed])

        # WandB 로거 초기화 (세션별)
        try:
            self.wandb_logger = AgenticRAGLogger(get_wandb_logger(session_id))
        except Exception as e:
            print(f"⚠️ WandB 로거 초기화 실패: {e}")
            self.wandb_logger = None

        # 노드 로직
        self.nodes = AgentNodes(
            llm_with_tools=self.llm_with_tools,
            tools=self.tools,
            wandb_logger=self.wandb_logger
        )

        # 그래프 빌드
        self.graph = self._build_graph()

        # 스트리밍 로직
        self.streaming = AgentStreaming(
            graph=self.graph,
            llm=self.llm,
            wandb_logger=self.wandb_logger
        )

    def _build_graph(self):
        """LangGraph 구성"""
        workflow = StateGraph(AgentState)

        # 노드
        workflow.add_node("agent", self.nodes.call_agent)
        workflow.add_node("tools", self.nodes.execute_tools)

        # 플로우
        workflow.set_entry_point("agent")

        workflow.add_conditional_edges(
            "agent",
            self.nodes.should_continue,
            {
                "continue": "tools",
                "end": END
            }
        )

        workflow.add_edge("tools", "agent")

        return workflow.compile()

    # ========================================
    # 실행 인터페이스
    # ========================================

    def run(self, question: str, session_id: Optional[str] = None) -> str:
        """Agent 실행 (non-streaming, backward compatibility)"""
        # 스트리밍을 내부적으로 실행하고 전체 결과만 반환
        full_answer = ""
        for chunk in self.run_stream(question, session_id):
            full_answer += chunk
        return full_answer

    def run_stream(self, question: str, session_id: Optional[str] = None):
        """Agent 실행 (streaming)"""
        return self.streaming.run_stream(question, session_id)

    # ========================================
    # 평가용 인터페이스
    # ========================================

    def run_with_metrics(self, question: str):
        """
        평가용 메서드: 답변, 검색 문서, 메트릭 반환

        Args:
            question: 사용자 질문

        Returns:
            {
                "answer": str,  # 최종 답변
                "retrieved_docs": List[Dict],  # 검색된 문서들
                "metrics": {
                    "response_time_ms": int,
                    "total_tokens": int,
                    "api_calls": int,
                    "search_iterations": int,
                    "mode": str
                }
            }
        """
        import time
        start_time = time.time()

        # 메트릭 추적 변수
        api_calls = 0
        total_tokens = 0
        retrieved_docs = []

        # 모드별 실행
        if self.mode == "vanilla":
            answer, docs, tokens, calls = self._run_vanilla(question)
        elif self.mode == "self_rag":
            answer, docs, tokens, calls = self._run_self_rag(question)
        else:  # current (기본)
            answer, docs, tokens, calls = self._run_current(question)

        retrieved_docs = docs
        total_tokens = tokens
        api_calls = calls

        response_time_ms = int((time.time() - start_time) * 1000)

        return {
            "answer": answer,
            "retrieved_docs": retrieved_docs,
            "metrics": {
                "response_time_ms": response_time_ms,
                "total_tokens": total_tokens,
                "api_calls": api_calls,
                "search_iterations": len(retrieved_docs) // 5 if retrieved_docs else 1,
                "mode": self.mode
            }
        }

    def _run_vanilla(self, question: str):
        """
        Vanilla RAG 실행 (검색 1회, 예외 조항 체크 X)

        Returns:
            (answer, retrieved_docs, total_tokens, api_calls)
        """
        from langchain_core.messages import SystemMessage, HumanMessage

        # 벡터 검색 1회만
        search_result = search_vector_db.invoke({"query": question})

        # 검색 실패 시 API 검색 (최소한의 fallback)
        if "VECTOR_DB_NO_MATCH" in search_result:
            # 질문에서 법령명 추출 시도
            law_name = self._extract_law_name(question)
            if law_name:
                search_result = search_law_by_api.invoke({
                    "law_name": law_name,
                    "query": question
                })
            else:
                search_result = "검색 실패: 법령명을 찾을 수 없습니다."

        # retrieved_docs 파싱
        retrieved_docs = self._parse_retrieved_docs(search_result)

        # 답변 생성 (검색 결과 기반)
        messages = [
            SystemMessage(content="""당신은 한국 법령 전문가입니다.
검색된 법령 내용을 기반으로 정확하고 간결하게 답변하세요.

필수 형식:
1. 결론 (1-2문장)
2. 근거 법령 (법령명 조문, 리스트)
3. 법령 내용 (원문 인용)

근거 법령을 반드시 명시하세요."""),
            HumanMessage(content=f"질문: {question}\n\n검색 결과:\n{search_result}")
        ]

        response = self.llm.invoke(messages)
        answer = self._extract_answer_text(response)

        # 메트릭
        total_tokens = self._count_tokens(messages, response)
        api_calls = 2  # search + generate

        return answer, retrieved_docs, total_tokens, api_calls

    def _run_current(self, question: str):
        """
        Current 시스템 실행 (예외 조항 체크)

        Returns:
            (answer, retrieved_docs, total_tokens, api_calls)
        """
        # 기존 그래프 실행 (스트리밍 모드)
        answer = ""
        for chunk in self.run_stream(question):
            # SSE 이벤트에서 answer_chunk만 추출
            if "data: " in chunk:
                import json
                try:
                    event_data = json.loads(chunk.split("data: ")[1])
                    if event_data.get("type") == "answer_chunk":
                        answer += event_data.get("text", "")
                except:
                    pass

        # 검색 결과 (vector_search_instance.last_results)
        retrieved_docs = self._get_last_search_results()

        # 메트릭 (대략적)
        total_tokens = len(answer) * 2  # 대략적 추정
        api_calls = 3  # search + check_exceptions + generate

        return answer, retrieved_docs, total_tokens, api_calls

    def _run_self_rag(self, question: str):
        """
        Self-RAG 실행 (검색 → 평가 → 재검색, 최대 3회)

        Returns:
            (answer, retrieved_docs, total_tokens, api_calls)
        """
        from langchain_core.messages import SystemMessage, HumanMessage
        import json

        max_iterations = 3
        all_retrieved_docs = []
        total_tokens = 0
        api_calls = 0

        # 초기 검색
        search_result = search_vector_db.invoke({"query": question})
        api_calls += 1
        retrieved_docs = self._parse_retrieved_docs(search_result)
        all_retrieved_docs.extend(retrieved_docs)

        for iteration in range(max_iterations):
            # LLM이 검색 결과를 평가
            eval_prompt = f"""검색 결과가 질문에 답하기에 충분한지 평가하세요.

질문: {question}

검색 결과:
{search_result}

평가 기준:
1. 질문의 핵심 조건이 모두 포함되었나?
2. 예외 조항이 필요한가?
3. 참조된 다른 조문이 있나?

응답 (JSON):
{{
  "sufficient": true/false,
  "reason": "이유",
  "additional_search": "추가 검색할 내용" (불충분할 경우)
}}"""

            eval_response = self.llm.invoke([HumanMessage(content=eval_prompt)])
            api_calls += 1

            eval_text = self._extract_answer_text(eval_response)

            # JSON 파싱
            try:
                if "```json" in eval_text:
                    eval_text = eval_text.split("```json")[1].split("```")[0].strip()
                eval_result = json.loads(eval_text)
            except:
                eval_result = {"sufficient": True, "reason": "파싱 실패"}

            # 충분하면 종료
            if eval_result.get("sufficient", True):
                break

            # 추가 검색
            additional_query = eval_result.get("additional_search", "")
            if additional_query:
                print(f"🔁 Self-RAG 반복 {iteration+1}: {additional_query}")
                search_result = search_vector_db.invoke({"query": additional_query})
                api_calls += 1
                retrieved_docs = self._parse_retrieved_docs(search_result)
                all_retrieved_docs.extend(retrieved_docs)

        # 최종 답변 생성
        all_content = "\n\n".join([doc.get("content", "") for doc in all_retrieved_docs])
        messages = [
            SystemMessage(content="""당신은 한국 법령 전문가입니다.
검색된 법령 내용을 기반으로 정확하고 간결하게 답변하세요.

필수 형식:
1. 결론 (1-2문장)
2. 근거 법령 (법령명 조문, 리스트)
3. 법령 내용 (원문 인용)"""),
            HumanMessage(content=f"질문: {question}\n\n검색 결과:\n{all_content}")
        ]

        response = self.llm.invoke(messages)
        api_calls += 1
        answer = self._extract_answer_text(response)

        total_tokens = self._count_tokens(messages, response)

        return answer, all_retrieved_docs, total_tokens, api_calls

    # ========================================
    # 헬퍼 메서드
    # ========================================

    def _extract_law_name(self, question: str):
        """질문에서 법령명 추출"""
        import re
        # 간단한 패턴 매칭 (예: "민법", "근로기준법")
        patterns = [
            r'(민법|형법|상법|헌법)',
            r'(근로기준법|노동조합법|산업안전보건법)',
            r'(임대차보호법|주택임대차보호법)',
            r'(\w+법)'
        ]
        for pattern in patterns:
            match = re.search(pattern, question)
            if match:
                return match.group(1)
        return None

    def _parse_retrieved_docs(self, search_result: str):
        """검색 결과 문자열을 문서 리스트로 파싱"""
        docs = []
        if "VECTOR_DB_NO_MATCH" in search_result or "검색 실패" in search_result:
            return docs

        # 간단한 파싱 (실제로는 더 정교하게)
        import re
        matches = re.findall(r'법령: (.+?)\n조문: (.+?)\n유사도: (.+?)\n내용: (.+?)(?:\n\n|\n관련|\Z)',
                            search_result, re.DOTALL)

        for law_name, article, similarity, content in matches:
            docs.append({
                "law_name": law_name.strip(),
                "article": article.strip(),
                "similarity": float(similarity.strip()) if similarity.strip() else 0.0,
                "content": content.strip()
            })

        return docs

    def _get_last_search_results(self):
        """마지막 검색 결과 가져오기"""
        if hasattr(vector_search_instance, 'last_results') and vector_search_instance.last_results:
            return vector_search_instance.last_results
        return []

    def _extract_answer_text(self, response):
        """LLM 응답에서 텍스트 추출"""
        if hasattr(response, 'content'):
            content = response.content
            if isinstance(content, list):
                text = ""
                for part in content:
                    if isinstance(part, dict) and 'text' in part:
                        text += part['text']
                return text
            elif isinstance(content, str):
                return content
        return str(response)

    def _count_tokens(self, messages, response):
        """토큰 수 대략 계산"""
        total_text = ""
        for msg in messages:
            total_text += msg.content if hasattr(msg, 'content') else str(msg)
        total_text += self._extract_answer_text(response)

        # 대략적 토큰 수 (한국어: 1토큰 ≈ 2자)
        return len(total_text) // 2
