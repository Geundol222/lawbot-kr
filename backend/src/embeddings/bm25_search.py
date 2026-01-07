"""
BM25 키워드 기반 검색

- rank_bm25를 사용한 전통적 키워드 검색
- kiwipiepy 형태소 분석 기반 토큰화
- Semantic search 보완용
"""

import os
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict
import threading
from rank_bm25 import BM25Okapi
from kiwipiepy import Kiwi
from supabase import create_client
from dotenv import load_dotenv

# 환경변수 로드 (.env가 없을 때는 이미 로드된 os.getenv 값 사용)
env_candidates = [
    Path(__file__).resolve().parents[2] / ".env",
    Path(__file__).resolve().parents[3] / ".env",
]
for env_path in env_candidates:
    if env_path.exists():
        load_dotenv(env_path)
        break

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")


class BM25Search:
    """BM25 키워드 검색 클래스"""

    def __init__(self, cache_path="backend/src/embeddings/bm25_index.pkl"):
        """
        Args:
            cache_path: BM25 인덱스 캐시 파일 경로
        """
        self.cache_path = cache_path
        self.kiwi = Kiwi()
        self.bm25 = None
        self.documents: List[Dict] = []  # [{'law_name': ..., 'article': ..., 'content': ...}]
        self._build_attempted = False
        self._cache_version = 2  # cache 포맷 변경 시 버전 업데이트
        self._building = False  # 중복 빌드 방지

        print("[BM25] 형태소 분석기 로드 완료")

    def tokenize(self, text: str) -> List[str]:
        """
        한국어 형태소 분석 (원형 기준)

        - 명사/동사/형용사/숫자 계열만 사용
        - 한 글자 불용 토큰 제거(숫자는 허용)
        """
        tokens: List[str] = []
        for token in self.kiwi.tokenize(text):
            if not token.tag:
                continue
            if token.tag[0] not in ["N", "V", "S"]:  # N=명사, V=동사, S=숫자/부호
                continue

            lemma = (token.lemma or token.form or "").strip()
            if not lemma:
                continue
            if len(lemma) == 1 and not lemma.isdigit():
                continue

            tokens.append(lemma)

        return tokens

    def _load_cache(self) -> bool:
        if not os.path.exists(self.cache_path):
            return False

        print(f"[BM25] 캐시에서 인덱스 로드 중... ({self.cache_path})")
        try:
            with open(self.cache_path, "rb") as f:
                cache_data = pickle.load(f)

            if cache_data.get("version") != self._cache_version:
                print("[BM25] 캐시 버전이 달라 재구축합니다...")
                return False

            tokenized_corpus = cache_data["tokenized_corpus"]
            self.documents = cache_data["documents"]
            self.bm25 = BM25Okapi(tokenized_corpus)
            print(f"[BM25] 인덱스 로드 완료! ({len(self.documents)}개 문서)")
            return True
        except Exception as e:
            print(f"[BM25] 캐시 로드 실패: {e}, 재구축합니다...")
            return False

    def _save_cache(self, tokenized_corpus: List[List[str]]):
        print(f"[BM25] 인덱스 캐시 저장 중... ({self.cache_path})")
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        with open(self.cache_path, "wb") as f:
            pickle.dump(
                {
                    "version": self._cache_version,
                    "tokenized_corpus": tokenized_corpus,
                    "documents": self.documents,
                },
                f,
            )

    def _load_all_documents(self, chunk_size: int = 1000) -> List[Dict]:
        print("[BM25] Supabase에서 문서 로드 중...")
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        docs: List[Dict] = []
        offset = 0

        while True:
            try:
                res = (
                    supabase.table("law_cache")
                    .select("law_name,article,title,content,mst")
                    .range(offset, offset + chunk_size - 1)
                    .execute()
                )
                batch = res.data or []
            except Exception as e:
                print(f"[BM25] ⚠️ Supabase 로드 실패: {e}")
                break

            if not batch:
                break

            docs.extend(batch)
            offset += chunk_size

            if len(batch) < chunk_size:
                break

            if offset % (chunk_size * 5) == 0:
                print(f"  진행: {offset}개 로드")

        return docs

    def build_index(self, force_rebuild: bool = False):
        """
        BM25 인덱스 구축

        Args:
            force_rebuild: True면 캐시 무시하고 재구축
        """
        if not force_rebuild and self._load_cache():
            return

        # 중복 빌드 방지
        if self._building:
            print("[BM25] 인덱스 빌드가 이미 진행 중입니다.")
            return

        self._building = True
        self.documents = self._load_all_documents()
        if not self.documents:
            print("[BM25] ⚠️ 문서가 없습니다!")
            self._building = False
            return

        print(f"[BM25] {len(self.documents)}개 문서 로드 완료")

        # 토큰화
        print("[BM25] 문서 토큰화 중...")
        tokenized_corpus: List[List[str]] = []
        for i, doc in enumerate(self.documents, 1):
            if i % 1000 == 0:
                print(f"  진행: {i}/{len(self.documents)}")

            full_text = f"{doc['law_name']} {doc['article']} {doc.get('title', '')} {doc['content']}"
            tokens = self.tokenize(full_text)
            tokenized_corpus.append(tokens)

        # BM25 인덱스 생성
        print("[BM25] BM25 인덱스 생성 중...")
        self.bm25 = BM25Okapi(tokenized_corpus)

        # 캐시 저장 (BM25 객체 대신 코퍼스만 저장해 용량/호환성 확보)
        self._save_cache(tokenized_corpus)
        print("[BM25] ✅ 인덱스 구축 완료!")
        self._building = False

    def start_background_build(self, force_rebuild: bool = False):
        """백그라운드에서 인덱스 빌드 (요청 차단 방지)"""
        if self.bm25 is not None and not force_rebuild:
            return
        if self._building:
            return

        def _worker():
            try:
                self.build_index(force_rebuild=force_rebuild)
            finally:
                self._building = False

        self._building = True
        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def search(self, query: str, top_k: int = 5, threshold: float = 0.0) -> List[Dict]:
        """
        BM25 검색

        Args:
            query: 검색 쿼리
            top_k: 반환할 결과 개수
            threshold: 최소 점수 (BM25 점수는 절대값이 아니므로 보통 0.0 사용)

        Returns:
            검색 결과 리스트
        """
        if self.bm25 is None:
            # 검색 시점에서는 빌드 요청만 던지고 기다리지 않음 (지연 방지)
            if not self._build_attempted:
                self._build_attempted = True
                print("[BM25] 인덱스가 없어 백그라운드 빌드를 시작합니다...")
                self.start_background_build()
            if self.bm25 is None:
                print("[BM25] ⚠️ 인덱스를 아직 준비하지 못했습니다. BM25 검색을 건너뜁니다.")
                return []

        tokenized_query = self.tokenize(query)
        if not tokenized_query:
            print(f"[BM25] ⚠️ 쿼리에서 유효한 토큰을 찾을 수 없습니다: {query}")
            return []

        scores = self.bm25.get_scores(tokenized_query)

        top_indices = np.argsort(scores)[::-1][: top_k * 2]  # 여유있게 2배

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score < threshold:
                continue
            if len(results) >= top_k:
                break

            doc = self.documents[idx]
            results.append(
                {
                    "law_name": doc["law_name"],
                    "article": doc["article"],
                    "title": doc.get("title", ""),
                    "content": doc["content"],
                    "mst": doc.get("mst"),
                    "score": score,
                }
            )

        return results


# 싱글톤 인스턴스
_bm25_instance = None


def get_bm25_instance():
    """BM25 검색 인스턴스 가져오기 (싱글톤)"""
    global _bm25_instance

    if _bm25_instance is None:
        _bm25_instance = BM25Search()
        # 자동 인덱스 빌드는 하지 않음 (명시적으로 build_index() 호출 필요)

    return _bm25_instance


def preload_bm25_index(force_rebuild: bool = False, background: bool = False):
    """
    서버 기동 시 BM25 인덱스를 미리 준비하기 위한 헬퍼

    Args:
        force_rebuild: 캐시 무시하고 재빌드 여부
        background: True면 백그라운드에서 비동기 빌드, False면 동기 빌드
    """
    bm25 = get_bm25_instance()
    if background:
        bm25.start_background_build(force_rebuild=force_rebuild)
    else:
        bm25.build_index(force_rebuild=force_rebuild)
    return bm25


# 테스트용
if __name__ == "__main__":
    print("=" * 60)
    print("BM25 검색 테스트")
    print("=" * 60)

    bm25 = BM25Search()
    bm25.build_index()

    test_queries = [
        "5인 미만 사업장 해고예고수당",
        "근로기준법 제26조",
        "부당해고",
        "상시 4명 이하",
    ]

    for query in test_queries:
        print(f"\n[쿼리] {query}")
        print("-" * 60)

        results = bm25.search(query, top_k=3)

        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['law_name']} {result['article']}")
            print(f"   점수: {result['score']:.2f}")
            print(f"   내용: {result['content'][:100]}...")
