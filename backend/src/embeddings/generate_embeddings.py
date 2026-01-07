"""
법령 임베딩 생성 및 Supabase 업로드 스크립트
- 조 단위 청킹 (맥락 완전 보존, 분석 결과 기반)
- 평균 조문 길이: 81자, 최대: 1564자 → 청킹 불필요
- 자동 캐시 초기화
"""
import os
import sys
import time
import json
import requests
from pathlib import Path
from typing import List, Dict, Optional
from tqdm import tqdm
import numpy as np
from sentence_transformers import SentenceTransformer
from supabase import create_client
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# ========================================
# 설정
# ========================================

LAW_API_SEARCH = os.getenv("LAW_API_SEARCH", "https://www.law.go.kr/DRF/lawSearch.do")
LAW_API_SERVICE = os.getenv("LAW_API_SERVICE", "https://www.law.go.kr/DRF/lawService.do")
LAW_API_OC = os.getenv("LAW_API_OC")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# 청킹 설정 (조 단위 청킹 - 더 이상 사용하지 않음)
# 분석 결과: 평균 81자, 96.8%가 500자 미만 → 조 전체를 하나의 청크로 사용
# CHUNK_SIZE = 500
# CHUNK_OVERLAP = 100

# 주요 법령 목록
MAJOR_LAWS = [
    # 민사법
    "민법", "민사소송법", "민사집행법", "가족관계의 등록 등에 관한 법률",
    # 형사법
    "형법", "형사소송법", "교통사고처리 특례법", "성폭력범죄의 처벌 등에 관한 특례법",
    # 부동산/임대차
    "주택임대차보호법", "주택임대차보호법 시행령",
    "상가건물 임대차보호법", "상가건물 임대차보호법 시행령",
    "부동산 실권리자명의 등기에 관한 법률", "공인중개사법", "공인중개사법 시행령", "공인중개사법 시행규칙",
    # 노동법
    "근로기준법", "근로기준법 시행령", "근로기준법 시행규칙",
    "최저임금법", "최저임금법 시행령", "최저임금법 시행규칙",
    "근로자퇴직급여 보장법", "근로자퇴직급여 보장법 시행령", "근로자퇴직급여 보장법 시행규칙",
    "산업안전보건법", "산업안전보건법 시행령", "산업안전보건법 시행규칙",
    "노동조합 및 노동관계조정법", "노동조합 및 노동관계조정법 시행령",
    "고용보험법", "고용보험법 시행령", "고용보험법 시행규칙",
    # 상법/회사법
    "상법", "상법 시행령",
    "주식회사 등의 외부감사에 관한 법률", "주식회사 등의 외부감사에 관한 법률 시행령",
    # 소비자/계약
    "소비자기본법", "소비자기본법 시행령", "소비자기본법 시행규칙",
    "전자상거래 등에서의 소비자보호에 관한 법률", "전자상거래 등에서의 소비자보호에 관한 법률 시행령", "전자상거래 등에서의 소비자보호에 관한 법률 시행규칙",
    "할부거래에 관한 법률", "할부거래에 관한 법률 시행령", "할부거래에 관한 법률 시행규칙",
    "방문판매 등에 관한 법률", "방문판매 등에 관한 법률 시행령", "방문판매 등에 관한 법률 시행규칙",
    # 금융/보험
    "은행법", "은행법 시행령",
    "보험업법", "보험업법 시행령", "보험업법 시행규칙",
    "자본시장과 금융투자업에 관한 법률", "자본시장과 금융투자업에 관한 법률 시행령",
    # 자동차/교통
    "자동차손해배상 보장법", "자동차손해배상 보장법 시행령", "자동차손해배상 보장법 시행규칙",
    "도로교통법", "도로교통법 시행령", "도로교통법 시행규칙",
    "자동차관리법", "자동차관리법 시행령", "자동차관리법 시행규칙",
    # 개인정보/통신
    "개인정보 보호법", "개인정보 보호법 시행령", "개인정보 보호법 시행규칙",
    "정보통신망 이용촉진 및 정보보호 등에 관한 법률", "정보통신망 이용촉진 및 정보보호 등에 관한 법률 시행령", "정보통신망 이용촉진 및 정보보호 등에 관한 법률 시행규칙",
    # 지적재산권
    "저작권법", "저작권법 시행령", "저작권법 시행규칙",
    "특허법", "특허법 시행령", "특허법 시행규칙",
    "상표법", "상표법 시행령", "상표법 시행규칙",
    # 기본법
    "대한민국헌법", "행정기본법", "행정기본법 시행령",
    "국가배상법", "국가배상법 시행령",
]

# ========================================
# 청킹 함수 (조 단위 - 더 이상 사용하지 않음)
# ========================================

# 조 전체를 하나의 청크로 사용하므로 텍스트 기반 청킹 불필요
# 분석 결과 대부분 조문이 충분히 짧음 (평균 81자)

# ========================================
# API 함수
# ========================================

def search_law_mst(law_name: str) -> Optional[Dict]:
    """법령명으로 MST 검색"""
    params = {
        'OC': LAW_API_OC,
        'target': 'law',
        'type': 'JSON',
        'query': law_name,
        'display': 10
    }

    try:
        response = requests.get(LAW_API_SEARCH, params=params, timeout=30)

        if not response.text:
            return None

        data = response.json()

        if 'LawSearch' not in data:
            return None

        law_list = data.get('LawSearch', {}).get('law', [])

        if not law_list:
            return None

        if isinstance(law_list, dict):
            law_list = [law_list]

        # 정확히 일치하는 법령 찾기
        for law in law_list:
            # API 응답 키: 법령명한글 (밑줄 없음!)
            if law.get('법령명한글') == law_name:
                return {
                    'mst': law.get('법령일련번호'),
                    'law_name': law.get('법령명한글')
                }

        return None

    except requests.exceptions.Timeout:
        print(f"[TIMEOUT] ({law_name})")
        return None
    except Exception as e:
        print(f"[ERROR] ({law_name}): {e}")
        return None


def get_all_articles(mst: str, law_name: str) -> tuple[List[Dict], List[str]]:
    """MST로 모든 조문 가져오기 (조 단위, 청킹 없음)

    Returns:
        tuple: (수집된 조문 리스트, 실패한 조문 리스트)
    """
    params = {
        'OC': LAW_API_OC,
        'target': 'law',
        'type': 'JSON',
        'MST': mst
    }

    failed_articles = []

    try:
        response = requests.get(LAW_API_SERVICE, params=params, timeout=30)

        if not response.text or response.text.strip() == '':
            error_msg = f"[WARN] 빈 응답 ({law_name})"
            print(error_msg)
            return [], [error_msg]

        try:
            data = response.json()
        except json.JSONDecodeError:
            error_msg = f"[WARN] JSON 파싱 실패 ({law_name})"
            print(error_msg)
            return [], [error_msg]

        if '법령' not in data:
            error_msg = f"[WARN] 법령 데이터 없음 ({law_name})"
            print(error_msg)
            return [], [error_msg]

        articles = []
        law_content = data.get('법령', {})
        조문 = law_content.get('조문')

        if not 조문:
            # 조문이 없는 경우 - 개정문만 있는지 확인
            available_keys = list(law_content.keys())
            if '개정문' in law_content and '조문' not in law_content:
                error_msg = f"[SKIP] {law_name}: 개정문만 존재 (조문 없음). 이 법령은 최근 개정되었으나 전체 본문이 API에 없습니다."
                print(error_msg)
                return [], [error_msg]
            elif '부칙' in law_content and '조문' not in law_content:
                error_msg = f"[SKIP] {law_name}: 부칙만 존재 (조문 없음)"
                print(error_msg)
                return [], [error_msg]
            else:
                error_msg = f"[WARN] {law_name}: 조문 구조 없음 (응답 키: {available_keys[:10]})"
                print(error_msg)
                return [], [error_msg]

        article_list = 조문.get('조문단위', [])

        if isinstance(article_list, dict):
            article_list = [article_list]

        print(f"\n[INFO] {law_name}: API에서 {len(article_list)}개 조문 수신")

        def flatten_text(value) -> str:
            """조문/항/호/목 등 중첩 구조를 모두 문자열로 평탄화."""
            if value is None:
                return ""
            if isinstance(value, str):
                return value
            if isinstance(value, list):
                return " ".join([flatten_text(v) for v in value if v is not None])
            if isinstance(value, dict):
                return " ".join([flatten_text(v) for v in value.values() if v is not None])
            return str(value)

        def extract_full_content(article_dict: Dict) -> str:
            parts: list[str] = []

            # 조문 본문
            base = flatten_text(article_dict.get("조문내용", ""))
            if base:
                parts.append(base)

            def collect_ho(ho_obj) -> list[str]:
                collected: list[str] = []
                if isinstance(ho_obj, dict):
                    ho_obj = [ho_obj]
                if isinstance(ho_obj, list):
                    for ho in ho_obj:
                        ho_text = flatten_text(ho.get("호내용", ""))
                        if ho_text:
                            collected.append(ho_text)
                        mok_list = ho.get("목", [])
                        if isinstance(mok_list, dict):
                            mok_list = [mok_list]
                        if isinstance(mok_list, list):
                            for mok in mok_list:
                                mok_text = flatten_text(mok.get("목내용", ""))
                                if mok_text:
                                    collected.append(mok_text)
                return collected

            # 항/호/목 본문
            hang = article_dict.get("항")
            if isinstance(hang, dict):
                hang = [hang]
            if isinstance(hang, list):
                for hang_item in hang:
                    hang_text = flatten_text(hang_item.get("항내용", ""))
                    if hang_text:
                        parts.append(hang_text)
                    parts.extend(collect_ho(hang_item.get("호", [])))
            elif hang:
                parts.append(flatten_text(hang))

            full = " ".join(parts)
            full = full.replace("<br/>", " ").replace("<br>", " ")
            return " ".join(full.split())

        for idx, article in enumerate(article_list, 1):
            article_num = article.get('조문번호', '')
            article_title = article.get('조문제목', '')
            조문여부 = article.get('조문여부', '')

            if not article_num:
                error_msg = f"[FAIL] {law_name}: 조문번호 없음 (인덱스 {idx})"
                print(error_msg)
                failed_articles.append(error_msg)
                continue

            # 조문여부가 '전문' 등으로 와도 수집 (스킵하지 않음)
            if 조문여부 and 조문여부 != '조문':
                print(f"[INFO] {law_name} 제{article_num}조: 조문여부={조문여부}, 수집 계속")

            full_content = extract_full_content(article)

            if not full_content:
                # API가 빈 문자열을 주는 경우 제목이라도 넣어서 누락을 막는다.
                full_content = f"{article_title}".strip()
                warn_msg = f"[WARN] {law_name} 제{article_num}조: 본문 없음 → 제목으로 대체"
                print(warn_msg)
                failed_articles.append(warn_msg)

            if full_content:
                articles.append({
                    'law_name': law_name,
                    'article': f'제{article_num}조',
                    'title': article_title if isinstance(article_title, str) else '',
                    'content': full_content,
                    'mst': mst
                })

                if idx % 10 == 0:
                    print(f"  [OK] {law_name}: {idx}/{len(article_list)}개 처리 중...")
            else:
                error_msg = f"[FAIL] {law_name} 제{article_num}조: 내용 없음 (0자)"
                print(error_msg)
                failed_articles.append(error_msg)

        print(f"[OK] {law_name}: {len(articles)}/{len(article_list)}개 조문 수집 완료")
        if failed_articles:
            print(f"[WARN] {law_name}: 실패 {len(failed_articles)}개")
            for log in failed_articles[:10]:
                print(f"  {log}" + (" ..." if len(failed_articles) > 10 and log == failed_articles[9] else ""))

        return articles, failed_articles

    except requests.exceptions.RequestException as e:
        error_msg = f"[ERROR] 네트워크 에러 ({law_name}): {e}"
        print(error_msg)
        return [], [error_msg]
    except Exception as e:
        error_msg = f"[ERROR] 조문 수집 실패 ({law_name}): {e}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return [], [error_msg]

# ========================================
# 메인 함수
# ========================================

def collect_law_articles() -> tuple[List[Dict], List[str]]:
    """법령 조문 수집

    Returns:
        tuple: (수집된 조문 리스트, 상세 로그 리스트)
    """
    from datetime import datetime

    # DEBUG 폴더 생성
    debug_dir = Path(__file__).parent.parent.parent.parent / "DEBUG"
    debug_dir.mkdir(exist_ok=True)

    # 로그 파일 경로
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = debug_dir / f"vector_db_rebuild_{timestamp}.log"

    logs = []

    def log(message: str, also_print: bool = True):
        """로그 기록 및 출력"""
        logs.append(message)
        if also_print:
            print(message)

    log("\n" + "="*60)
    log("[START] 법령 데이터 수집 시작...")
    log(f"[INFO] 로그 파일: {log_file}")
    log("="*60 + "\n")

    all_articles = []
    failed_laws = []
    all_failed_articles = []
    success_count = 0
    total_articles_received = 0
    total_articles_saved = 0

    for law_name in tqdm(MAJOR_LAWS, desc="법령 수집"):
        log(f"\n{'='*60}")
        log(f"[PROCESSING] {law_name}")
        log(f"{'='*60}")

        # MST 검색
        law_info = search_law_mst(law_name)

        if not law_info:
            error_msg = f"[FAIL] {law_name}: MST를 찾을 수 없습니다"
            log(error_msg)
            failed_laws.append(law_name)
            all_failed_articles.append(error_msg)
            time.sleep(3)  # API 호출 간격 늘림 (2초 → 3초)
            continue

        log(f"[OK] {law_name}: MST = {law_info['mst']}")

        # 조문 수집 (조 단위)
        articles, failed_articles = get_all_articles(law_info['mst'], law_name)

        total_articles_received += len(articles) + len(failed_articles)
        total_articles_saved += len(articles)

        if articles:
            all_articles.extend(articles)
            success_count += 1
            log(f"[SUCCESS] {law_name}: {len(articles)}개 조문 수집 완료")

            # 수집된 조문 번호 로그
            article_nums = [a['article'] for a in articles]
            log(f"  수집된 조문: {', '.join(article_nums[:10])}" +
                (f"... (외 {len(article_nums)-10}개)" if len(article_nums) > 10 else ""))
        else:
            error_msg = f"[WARN] {law_name}: 조문이 없습니다"
            log(error_msg)
            failed_laws.append(law_name)

        # 실패한 조문 기록
        if failed_articles:
            log(f"[FAILED_ARTICLES] {law_name}: {len(failed_articles)}개 조문 실패")
            for fail_msg in failed_articles:
                log(f"  {fail_msg}")
                all_failed_articles.append(fail_msg)

        time.sleep(3)  # API 호출 간격 늘림 (2초 → 3초)

    # 최종 요약
    log("\n" + "="*60)
    log("[DONE] 법령 데이터 수집 완료!")
    log("="*60)
    log(f"[SUMMARY]")
    log(f"  - 성공한 법령: {success_count}/{len(MAJOR_LAWS)}개")
    log(f"  - 실패한 법령: {len(failed_laws)}개")
    log(f"  - API에서 받은 총 조문: {total_articles_received}개")
    log(f"  - 저장할 조문: {total_articles_saved}개")
    log(f"  - 실패한 조문: {len(all_failed_articles)}개")

    if failed_laws:
        log(f"\n[FAILED_LAWS] 실패한 법령 목록:")
        for law in failed_laws:
            log(f"   - {law}")

    if all_failed_articles:
        log(f"\n[FAILED_ARTICLES] 실패한 조문 상세:")
        for fail_msg in all_failed_articles[:50]:  # 최대 50개만 출력
            log(f"   {fail_msg}")
        if len(all_failed_articles) > 50:
            log(f"   ... (외 {len(all_failed_articles)-50}개)")

    log("="*60 + "\n")

    # 로그 파일 저장
    try:
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(logs))
        log(f"[OK] 로그 저장 완료: {log_file}")
    except Exception as e:
        print(f"[ERROR] 로그 저장 실패: {e}")

    return all_articles, logs


def generate_embeddings(articles: List[Dict]) -> tuple:
    """임베딩 생성"""
    print("\n" + "="*60)
    print("[LOAD] 임베딩 모델 로드 중...")
    print("="*60 + "\n")

    model = SentenceTransformer('intfloat/multilingual-e5-large-instruct')

    print("[OK] 모델 로드 완료!")
    print(f"[INFO] 임베딩 차원: {model.get_sentence_embedding_dimension()}")

    print("\n" + "="*60)
    print("[EMBED] 임베딩 생성 중...")
    print("="*60 + "\n")

    embeddings = []

    for article in tqdm(articles, desc="임베딩 생성"):
        # 텍스트 구성
        text = f"법령: {article['law_name']}, 조문: {article['article']}"

        if article['title']:
            text += f", 제목: {article['title']}"

        text += f", 내용: {article['content']}"

        # 임베딩
        embedding = model.encode(text, convert_to_numpy=True)
        embeddings.append(embedding)

    embeddings = np.array(embeddings)

    print(f"\n[OK] 임베딩 생성 완료!")
    print(f"[INFO] Shape: {embeddings.shape}")

    return embeddings, model


def upload_to_supabase(
    embeddings: np.ndarray,
    metadata: List[Dict],
    table_name: str = "law_cache",
    clear_existing: bool = True
):
    """Supabase에 업로드"""
    print("\n" + "="*60)
    print("[UPLOAD] Supabase 업로드 중...")
    print("="*60 + "\n")

    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    # 기존 데이터 삭제
    if clear_existing:
        print("[DELETE] 기존 데이터 삭제 중...")
        try:
            result = supabase.table(table_name).delete().neq('id', 0).execute()
            print("[OK] 기존 데이터 삭제 완료!")
        except Exception as e:
            print(f"[WARN] 삭제 실패: {e}")

    # 업로드
    batch_size = 50
    upload_count = 0
    failed_count = 0

    print(f"\n[START] 업로드 시작... (총 {len(embeddings)}개)")

    for i in tqdm(range(0, len(embeddings), batch_size), desc="업로드"):
        batch_embeddings = embeddings[i:i+batch_size]
        batch_metadata = metadata[i:i+batch_size]

        for emb, meta in zip(batch_embeddings, batch_metadata):
            try:
                supabase.table(table_name).upsert({
                    "law_name": meta['law_name'],
                    "article": meta['article'],
                    "title": meta.get('title', '')[:200] if meta.get('title') else '',
                    "content": meta['content'],  # 전체 청크 내용
                    "mst": meta['mst'],
                    "embedding": emb.tolist()
                }, on_conflict='law_name,article').execute()

                upload_count += 1

            except Exception as e:
                failed_count += 1
                if failed_count <= 3:
                    print(f"\n[WARN] 실패: {meta['law_name']} {meta['article']}")
                    error_msg = str(e)
                    if len(error_msg) > 100:
                        error_msg = error_msg[:100] + "..."
                    print(f"   에러: {error_msg}")

        time.sleep(0.5)

    print(f"\n" + "="*60)
    print(f"[DONE] 업로드 완료!")
    print(f"[OK] 성공: {upload_count}/{len(embeddings)}개")
    print(f"[WARN] 실패: {failed_count}개")
    print("="*60)


def main():
    """메인 실행 함수"""
    # 환경변수 확인
    if not all([LAW_API_OC, SUPABASE_URL, SUPABASE_ANON_KEY]):
        print("[ERROR] 환경변수를 확인해주세요:")
        print("   - LAW_API_OC")
        print("   - SUPABASE_URL")
        print("   - SUPABASE_ANON_KEY")
        return

    # 1. 법령 수집
    print("\n" + "="*80)
    print(" "*20 + "VectorDB 완전 재구축 시작")
    print("="*80 + "\n")

    articles, logs = collect_law_articles()

    if not articles:
        print("[ERROR] 수집된 조문이 없습니다!")
        return

    # 2. 임베딩 생성
    embeddings, model = generate_embeddings(articles)

    # 3. Supabase 업로드
    upload_to_supabase(
        embeddings,
        articles,
        table_name="law_cache",
        clear_existing=True  # 자동 초기화
    )

    # 4. 샘플 테스트
    print("\n" + "="*60)
    print("[TEST] 샘플 검색 테스트...")
    print("="*60 + "\n")

    # 테스트 1: 야근수당
    test_query = "야근수당은 얼마나 받을 수 있나요?"
    query_embedding = model.encode(test_query, convert_to_numpy=True)

    similarities = np.dot(embeddings, query_embedding) / (
        np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_embedding)
    )

    top_indices = np.argsort(similarities)[-3:][::-1]

    print(f"질문 1: {test_query}\n")
    for idx in top_indices:
        article = articles[idx]
        print(f"  {article['law_name']} {article['article']} (유사도: {similarities[idx]:.3f})")
        print(f"  내용: {article['content'][:80]}...\n")

    # 테스트 2: 해고 예고수당 (제26조 확인)
    print("\n" + "-"*60)
    test_query2 = "해고 예고수당"
    query_embedding2 = model.encode(test_query2, convert_to_numpy=True)

    similarities2 = np.dot(embeddings, query_embedding2) / (
        np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_embedding2)
    )

    top_indices2 = np.argsort(similarities2)[-5:][::-1]

    print(f"질문 2: {test_query2}\n")
    for idx in top_indices2:
        article = articles[idx]
        print(f"  {article['law_name']} {article['article']} (유사도: {similarities2[idx]:.3f})")
        if '제26조' in article['article'] and '근로기준법' in article['law_name']:
            print(f"  ✅ 근로기준법 제26조 발견!")
        print(f"  내용: {article['content'][:80]}...\n")

    # 제26조 존재 여부 확인
    has_26 = any('제26조' in a['article'] and '근로기준법' in a['law_name'] for a in articles)
    if has_26:
        print("✅ 근로기준법 제26조가 VectorDB에 저장되었습니다!")
    else:
        print("❌ 근로기준법 제26조가 VectorDB에 없습니다!")

    print("\n" + "="*60)
    print("[DONE] 모든 작업 완료!")
    print("="*60)


if __name__ == "__main__":
    main()
