"""
법령 임베딩 생성 및 Supabase 업로드 스크립트
- 전체 조문 청킹 (1000자 제한 해결)
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

# 청킹 설정
CHUNK_SIZE = 500  # 청크 크기 (문자)
CHUNK_OVERLAP = 100  # 청크 오버랩

# 주요 법령 목록
MAJOR_LAWS = [
    # 민사법
    "민법", "민사소송법", "민사집행법", "가족관계의 등록 등에 관한 법률",
    # 형사법
    "형법", "형사소송법", "교통사고처리 특례법", "성폭력범죄의 처벌 등에 관한 특례법",
    # 부동산/임대차
    "주택임대차보호법", "상가건물 임대차보호법", "부동산 실권리자명의 등기에 관한 법률", "공인중개사법",
    # 노동법
    "근로기준법", "최저임금법", "근로자퇴직급여 보장법", "산업안전보건법",
    "노동조합 및 노동관계조정법", "고용보험법",
    # 상법/회사법
    "상법", "주식회사 등의 외부감사에 관한 법률",
    # 소비자/계약
    "소비자기본법", "전자상거래 등에서의 소비자보호에 관한 법률",
    "할부거래에 관한 법률", "방문판매 등에 관한 법률",
    # 금융/보험
    "은행법", "보험업법", "자본시장과 금융투자업에 관한 법률",
    # 자동차/교통
    "자동차손해배상 보장법", "도로교통법", "자동차관리법",
    # 개인정보/통신
    "개인정보 보호법", "정보통신망 이용촉진 및 정보보호 등에 관한 법률",
    # 지적재산권
    "저작권법", "특허법", "상표법",
    # 기본법
    "대한민국헌법", "행정기본법", "국가배상법",
]

# ========================================
# 청킹 함수
# ========================================

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    긴 텍스트를 청크로 나누기

    Args:
        text: 원본 텍스트
        chunk_size: 청크 크기
        overlap: 청크 간 오버랩

    Returns:
        청크 리스트
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap

    return chunks

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
            if law.get('법령명한글') == law_name:
                return {
                    'mst': law.get('법령일련번호'),
                    'law_name': law.get('법령명한글')
                }

        return None

    except requests.exceptions.Timeout:
        print(f"⏱️ 타임아웃 ({law_name})")
        return None
    except Exception as e:
        print(f"⚠️ 에러 ({law_name}): {e}")
        return None


def get_all_articles(mst: str, law_name: str) -> List[Dict]:
    """MST로 모든 조문 가져오기 (전체 내용, 청킹 적용)"""
    params = {
        'OC': LAW_API_OC,
        'target': 'law',
        'type': 'JSON',
        'MST': mst
    }

    try:
        response = requests.get(LAW_API_SERVICE, params=params, timeout=30)

        if not response.text or response.text.strip() == '':
            print(f"⚠️ 빈 응답 ({law_name})")
            return []

        try:
            data = response.json()
        except json.JSONDecodeError:
            print(f"⚠️ JSON 파싱 실패 ({law_name})")
            return []

        if '법령' not in data:
            print(f"⚠️ 법령 데이터 없음 ({law_name})")
            return []

        articles = []
        law_content = data.get('법령', {})
        조문 = law_content.get('조문', {})

        if not 조문:
            return []

        article_list = 조문.get('조문단위', [])

        if isinstance(article_list, dict):
            article_list = [article_list]

        for article in article_list:
            article_num = article.get('조문번호', '')
            article_title = article.get('조문제목', '')

            # 항 내용 합치기
            항_list = article.get('항', [])
            if isinstance(항_list, dict):
                항_list = [항_list]

            content_parts = []
            for 항 in 항_list:
                항_content = 항.get('항내용', '')

                # 항내용이 리스트인 경우 처리
                if isinstance(항_content, list):
                    항_content = ' '.join([str(c) for c in 항_content if c])
                elif not isinstance(항_content, str):
                    항_content = str(항_content)

                if 항_content:
                    # HTML 태그 제거
                    항_content = 항_content.replace('<br/>', ' ')
                    항_content = 항_content.replace('<br>', ' ')
                    content_parts.append(항_content)

            full_content = ' '.join(content_parts)

            if full_content and len(full_content) > 10:
                # ⭐ 청킹 적용 ⭐
                chunks = chunk_text(full_content)

                for chunk_idx, chunk in enumerate(chunks):
                    chunk_suffix = f"_part{chunk_idx + 1}" if len(chunks) > 1 else ""

                    articles.append({
                        'law_name': law_name,
                        'article': f'제{article_num}조{chunk_suffix}',
                        'title': article_title if isinstance(article_title, str) else '',
                        'content': chunk,
                        'full_content': full_content,  # 전체 내용도 저장
                        'chunk_index': chunk_idx,
                        'total_chunks': len(chunks),
                        'mst': mst
                    })

        return articles

    except requests.exceptions.RequestException as e:
        print(f"⚠️ 네트워크 에러 ({law_name}): {e}")
        return []
    except Exception as e:
        print(f"⚠️ 조문 수집 실패 ({law_name}): {e}")
        import traceback
        traceback.print_exc()
        return []

# ========================================
# 메인 함수
# ========================================

def collect_law_articles() -> List[Dict]:
    """법령 조문 수집"""
    print("\n" + "="*60)
    print("📚 법령 데이터 수집 시작...")
    print("="*60 + "\n")

    all_articles = []
    failed_laws = []
    success_count = 0

    for law_name in tqdm(MAJOR_LAWS, desc="법령 수집"):
        # MST 검색
        law_info = search_law_mst(law_name)

        if not law_info:
            print(f"❌ {law_name}: MST를 찾을 수 없습니다")
            failed_laws.append(law_name)
            time.sleep(2)
            continue

        # 조문 수집 (청킹 적용)
        articles = get_all_articles(law_info['mst'], law_name)

        if articles:
            all_articles.extend(articles)
            success_count += 1
            print(f"✅ {law_name}: {len(articles)}개 청크 생성")
        else:
            print(f"⚠️ {law_name}: 조문이 없습니다")
            failed_laws.append(law_name)

        time.sleep(2)  # Rate Limit 방지

    print("\n" + "="*60)
    print(f"🎉 총 {len(all_articles)}개 청크 수집 완료!")
    print(f"✅ 성공한 법령: {success_count}/{len(MAJOR_LAWS)}개")
    print(f"⚠️ 실패한 법령: {len(failed_laws)}개")
    if failed_laws:
        print(f"   실패 목록:")
        for law in failed_laws:
            print(f"   - {law}")
    print("="*60 + "\n")

    return all_articles


def generate_embeddings(articles: List[Dict]) -> tuple:
    """임베딩 생성"""
    print("\n" + "="*60)
    print("🧠 임베딩 모델 로드 중...")
    print("="*60 + "\n")

    model = SentenceTransformer('intfloat/multilingual-e5-large-instruct')

    print("✅ 모델 로드 완료!")
    print(f"📊 임베딩 차원: {model.get_sentence_embedding_dimension()}")

    print("\n" + "="*60)
    print("🔮 임베딩 생성 중...")
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

    print(f"\n✅ 임베딩 생성 완료!")
    print(f"📊 Shape: {embeddings.shape}")

    return embeddings, model


def upload_to_supabase(
    embeddings: np.ndarray,
    metadata: List[Dict],
    table_name: str = "law_cache",
    clear_existing: bool = True
):
    """Supabase에 업로드"""
    print("\n" + "="*60)
    print("☁️ Supabase 업로드 중...")
    print("="*60 + "\n")

    supabase = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    # 기존 데이터 삭제
    if clear_existing:
        print("🗑️ 기존 데이터 삭제 중...")
        try:
            result = supabase.table(table_name).delete().neq('id', 0).execute()
            print("✅ 기존 데이터 삭제 완료!")
        except Exception as e:
            print(f"⚠️ 삭제 실패: {e}")

    # 업로드
    batch_size = 50
    upload_count = 0
    failed_count = 0

    print(f"\n📤 업로드 시작... (총 {len(embeddings)}개)")

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
                    print(f"\n⚠️ 실패: {meta['law_name']} {meta['article']}")
                    error_msg = str(e)
                    if len(error_msg) > 100:
                        error_msg = error_msg[:100] + "..."
                    print(f"   에러: {error_msg}")

        time.sleep(0.5)

    print(f"\n" + "="*60)
    print(f"🎉 업로드 완료!")
    print(f"✅ 성공: {upload_count}/{len(embeddings)}개")
    print(f"⚠️ 실패: {failed_count}개")
    print("="*60)


def main():
    """메인 실행 함수"""
    # 환경변수 확인
    if not all([LAW_API_OC, SUPABASE_URL, SUPABASE_ANON_KEY]):
        print("❌ 환경변수를 확인해주세요:")
        print("   - LAW_API_OC")
        print("   - SUPABASE_URL")
        print("   - SUPABASE_ANON_KEY")
        return

    # 1. 법령 수집
    articles = collect_law_articles()

    if not articles:
        print("❌ 수집된 조문이 없습니다!")
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
    print("🧪 샘플 검색 테스트...")
    print("="*60 + "\n")

    test_query = "야근수당은 얼마나 받을 수 있나요?"
    query_embedding = model.encode(test_query, convert_to_numpy=True)

    # 코사인 유사도
    similarities = np.dot(embeddings, query_embedding) / (
        np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_embedding)
    )

    # 상위 3개
    top_indices = np.argsort(similarities)[-3:][::-1]

    print(f"질문: {test_query}\n")
    print("검색 결과:")

    for idx in top_indices:
        article = articles[idx]
        print(f"\n{article['law_name']} {article['article']}")
        print(f"유사도: {similarities[idx]:.3f}")
        print(f"내용: {article['content'][:100]}...")

    print("\n" + "="*60)
    print("✅ 모든 작업 완료! 🎉")
    print("="*60)


if __name__ == "__main__":
    main()
