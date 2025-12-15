from sentence_transformers import SentenceTransformer, CrossEncoder
from supabase import create_client
import numpy as np
import time
from typing import List, Dict

from src.config import SUPABASE_URL, SUPABASE_KEY
from src.monitoring import get_wandb_logger, VectorSearchLogger
from src.embeddings.bm25_search import get_bm25_instance

class VectorSearch:
    def __init__(self):
        # sentence-transformers 올바른 클래스명 사용
        self.model = SentenceTransformer("intfloat/multilingual-e5-large-instruct")
        # reranker (Korean BGE)
        self.reranker = CrossEncoder("dragonkue/bge-reranker-v2-m3-ko")
        # create_client는 (url, key) 순서를 사용
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        # 마지막 검색 결과를 보관해 후속 로깅/저장에 활용
        self.last_results = []
        # BM25 인스턴스 (필요 시 lazy build)
        self.bm25 = get_bm25_instance()

        # WandB 로거 초기화
        try:
            self.wandb_logger = VectorSearchLogger(get_wandb_logger())
        except Exception:
            self.wandb_logger = None

    def search(self, query: str, top_k: int = 5, threshold: float = 0.0):
        """유사한 법령 검색 (Semantic + BM25 병렬 후 rerank)

        Args:
            query: 검색 질문
            top_k: 반환할 최대 결과 수
            threshold: 유사도 임계값 (semantic)
        """
        search_start = time.time()
        self.last_results = []

        # 질문 임베딩
        embedding_start = time.time()
        query_emb = np.array(self.model.encode(query), dtype=np.float32).tolist()
        embedding_time = time.time() - embedding_start

        # Semantic (RPC)
        semantic_results, search_method = self._semantic_search_rpc(query, query_emb, top_k, threshold)

        # BM25 (키워드)
        bm25_results = []
        try:
            bm25_results = self.bm25.search(query, top_k=top_k * 3)
        except Exception as e:
            print(f"⚠️ BM25 검색 실패: {e}")

        # 병합 후 rerank
        combined = self._merge_results(semantic_results, bm25_results, max_candidates=top_k * 6)
        reranked = self._rerank(query, combined, top_k)

        # WandB 로깅
        if self.wandb_logger:
            search_time = time.time() - search_start
            top_score = reranked[0].get("score", 0.0) if reranked else 0.0
            self.wandb_logger.log_search(
                query=query,
                search_time=search_time,
                embedding_time=embedding_time,
                results_count=len(reranked),
                top_similarity=top_score,
                search_method=f"{search_method}+BM25+rerank",
                deduplication_count=0
            )

        self.last_results = reranked
        return reranked

    def _semantic_search_rpc(self, query: str, query_emb: List[float], top_k: int, threshold: float):
        """Supabase RPC 기반 semantic 검색 (폴백 포함)"""
        search_method = "RPC"
        try:
            result = self.supabase.rpc(
                "match_law_documents",
                {
                    "query_embedding": query_emb,
                    "match_threshold": threshold,
                    "match_count": top_k * 3,
                },
            ).execute()

            if result.data:
                # 디버깅 로그
                print(f"\n[DEBUG] RPC에서 받은 원본 결과 ({len(result.data)}개):")
                for idx, r in enumerate(result.data[:15], 1):
                    print(f"  [{idx}] {r.get('law_name')} {r.get('article')} - 유사도: {r.get('similarity', 0):.3f}")

                # 제26조 체크
                has_26 = any(
                    r.get("article") == "제26조" and "근로기준법" in r.get("law_name", "")
                    for r in result.data
                )
                if has_26:
                    article_26 = next(
                        (r for r in result.data if r.get("article") == "제26조" and "근로기준법" in r.get("law_name", "")),
                        None,
                    )
                    if article_26:
                        print(f"[DEBUG] ✅ 근로기준법 제26조 발견! 유사도: {article_26.get('similarity', 0):.3f}")
                else:
                    print(f"[DEBUG] ❌ 근로기준법 제26조가 RPC 결과에 없음!")

                return result.data, search_method

        except Exception as e:
            print(f"⚠️ RPC 호출 실패, 폴백 방식 사용: {e}")
            search_method = "Fallback"

        # 폴백: 수동 유사도 계산
        query_vec = np.array(query_emb, dtype=np.float32)
        raw = self.supabase.table("law_cache").select("*").execute()

        sims = []
        for row in raw.data:
            emb_raw = row.get("embedding")
            try:
                if isinstance(emb_raw, str):
                    import json
                    emb_raw = json.loads(emb_raw)
                law_emb = np.array(emb_raw, dtype=np.float32)
            except Exception:
                continue
            if law_emb.size == 0:
                continue

            sim = float(np.dot(law_emb, query_vec) / (np.linalg.norm(law_emb) * np.linalg.norm(query_vec)))
            if sim >= threshold:
                sims.append(
                    {
                        "law_name": row.get("law_name"),
                        "article": row.get("article"),
                        "mst": row.get("mst"),
                        "content": row.get("content"),
                        "similarity": sim,
                        "title": row.get("title", ""),
                    }
                )

        sims.sort(key=lambda x: x["similarity"], reverse=True)
        return sims[: top_k * 3], search_method

    def _merge_results(self, semantic_results: List[Dict], bm25_results: List[Dict], max_candidates: int) -> List[Dict]:
        """semantic + BM25 결과를 (law_name, article) 기준으로 병합"""
        merged = {}

        def add_item(item: Dict, source: str):
            key = f"{item.get('law_name')}:{item.get('article')}"
            existing = merged.get(key, {})
            existing_sources = existing.get("source", set())
            if not isinstance(existing_sources, set):
                existing_sources = set(existing_sources) if existing_sources else set()
            merged[key] = {
                "law_name": item.get("law_name"),
                "article": item.get("article"),
                "mst": item.get("mst"),
                "title": item.get("title", ""),
                "content": item.get("content"),
                "semantic_score": item.get("similarity"),
                "bm25_score": item.get("score"),
                "source": sorted(list(existing_sources | {source})),
            }

        for r in semantic_results or []:
            add_item(r, "semantic")
        for r in bm25_results or []:
            add_item(r, "bm25")

        # 상위 후보만 유지 (semantic 우선, 다음 bm25)
        candidates = list(merged.values())
        candidates.sort(
            key=lambda x: (x.get("semantic_score", 0) or 0, x.get("bm25_score", 0) or 0),
            reverse=True,
        )
        return candidates[:max_candidates]

    def _rerank(self, query: str, candidates: List[Dict], top_k: int) -> List[Dict]:
        """CrossEncoder 기반 rerank"""
        if not candidates:
            return []

        try:
            pairs = []
            for c in candidates:
                text = f"{c.get('law_name','')} {c.get('article','')} {c.get('title','')} {self._truncate(c.get('content',''))}"
                pairs.append([query, text])

            scores = self.reranker.predict(pairs)
            for cand, score in zip(candidates, scores):
                cand["score"] = float(score)

            candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        except Exception as e:
            print(f"⚠️ Rerank 실패, semantic 점수로 정렬합니다: {e}")
            for cand in candidates:
                cand["score"] = cand.get("semantic_score", 0) or 0.0
            candidates.sort(key=lambda x: x.get("score", 0), reverse=True)

        return candidates[:top_k]

    @staticmethod
    def _truncate(text: str, max_len: int = 600):
        """리랭킹 입력 길이 제한"""
        return text[:max_len]

    def _deduplicate_chunks(self, results: list, top_k: int) -> list:
        """
        중복 제거 (조 단위 청킹이므로 중복 없음, 유사도 순으로 정렬만 수행)

        Args:
            results: 검색 결과 리스트
            top_k: 반환할 최대 결과 수

        Returns:
            중복 제거된 결과
        """
        # 조 단위 청킹이므로 _part suffix가 없음
        # 동일 조문 중복도 없으므로 유사도 순 정렬만 수행
        seen_articles = {}

        for item in results:
            law_name = item.get("law_name")
            article = item.get("article", "")
            key = f"{law_name}:{article}"

            # 같은 조문이 없거나, 더 높은 유사도면 업데이트 (이론상 중복 없음)
            if key not in seen_articles or item.get("similarity", 0) > seen_articles[key].get("similarity", 0):
                seen_articles[key] = item

        # 유사도 순으로 정렬하여 반환
        deduplicated = list(seen_articles.values())
        deduplicated.sort(key=lambda x: x.get("similarity", 0), reverse=True)

        return deduplicated[:top_k]
