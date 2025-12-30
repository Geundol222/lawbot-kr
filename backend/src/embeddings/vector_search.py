from sentence_transformers import SentenceTransformer, CrossEncoder
from supabase import create_client
import numpy as np
import time
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor

from src.config import SUPABASE_URL, SUPABASE_KEY
from src.monitoring import get_wandb_logger, VectorSearchLogger
from src.embeddings.bm25_search import get_bm25_instance
from src.config import get_llm, llm_invoke_with_retry

class VectorSearch:
    def __init__(self):
        # sentence-transformers 올바른 클래스명 사용
        self.model = SentenceTransformer("intfloat/multilingual-e5-large-instruct")
        # reranker (Korean BGE)
        self.reranker = CrossEncoder("dragonkue/bge-reranker-v2-m3-ko")
        # create_client는 (url, key) 순서를 사용 (타임아웃 30초)
        self.supabase = create_client(
            SUPABASE_URL,
            SUPABASE_KEY,
            options={
                "postgrest_client_timeout": 30,
                "storage_client_timeout": 30,
            }
        )
        # 마지막 검색 결과를 보관해 후속 로깅/저장에 활용
        self.last_results = []
        # BM25 인스턴스 (필요 시 lazy build)
        self.bm25 = get_bm25_instance()

        # WandB 로거 초기화
        try:
            self.wandb_logger = VectorSearchLogger(get_wandb_logger())
        except Exception:
            self.wandb_logger = None

    def _extract_subqueries(self, query: str) -> List[str]:
        """
        LLM으로 핵심 키워드/구를 뽑되, 실패 시 단순 분할로 대체한다.
        - 원문 쿼리는 항상 포함
        - JSON 배열 형태로만 응답을 기대
        """
        import re, json

        subs: List[str] = []
        base = query.strip()
        if base:
            subs.append(base)

        prompt = (
            "주어진 질문에서 핵심 키워드나 구를 2~5개 JSON 배열로만 답하세요. "
            "불필요한 설명은 금지합니다.\n"
            f"질문: {query}\n"
            "예시: [\"5인 미만 사업장\", \"해고예고수당\"]"
        )

        try:
            llm = get_llm("flash-lite")
            response = llm_invoke_with_retry(llm, prompt)
            raw = response if isinstance(response, str) else getattr(response, "content", "")
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                for p in parsed:
                    if isinstance(p, str):
                        t = p.strip()
                        if 2 <= len(t) <= 80:
                            subs.append(t)
        except Exception:
            # LLM 실패 시 구두점 기반 분할
            pieces = re.split(r"[\\n\\r\\t,.;?/]+", query)
            for p in pieces:
                p = p.strip()
                if 4 <= len(p) <= 80:
                    subs.append(p)

        # 중복 제거
        seen = set()
        uniq = []
        for s in subs:
            norm = s.lower()
            if norm in seen:
                continue
            uniq.append(s)
            seen.add(norm)

        return uniq[:4]
    
    def search(self, query: str, top_k: int = 5, threshold: float = 0.0):
        """유사한 법령 검색 (하위 쿼리 병렬: Semantic+BM25 → 전체 rerank)"""
        search_start = time.time()
        self.last_results = []

        subqueries = self._extract_subqueries(query)
        print(f"[DEBUG] 서브쿼리 {len(subqueries)}개: {subqueries}")

        all_semantic = []
        all_bm25 = []
        embedding_time = 0.0
        search_method = "semantic"

        # 서브쿼리 단위로 병렬 실행
        def run_one(qsub: str):
            emb_start = time.time()
            q_emb = np.array(self.model.encode(qsub), dtype=np.float32).tolist()
            emb_dur = time.time() - emb_start
            sem_res, smethod = self._semantic_search_rpc(qsub, q_emb, top_k, threshold)
            bm25_res = self._bm25_search_safe(qsub, top_k * 3)
            return emb_dur, sem_res, bm25_res, smethod

        with ThreadPoolExecutor(max_workers=min(4, len(subqueries) * 2)) as executor:
            futures = [executor.submit(run_one, sq) for sq in subqueries]
            for fut in futures:
                emb_dur, sem_res, bm25_res, smethod = fut.result()
                embedding_time += emb_dur
                all_semantic.extend(sem_res)
                all_bm25.extend(bm25_res)
                search_method = smethod
                print(f"[DEBUG] 서브쿼리 결과: semantic {len(sem_res)}개, bm25 {len(bm25_res)}개")

        combined = self._merge_results(all_semantic, all_bm25, max_candidates=top_k * 6 * len(subqueries))
        print(f"[DEBUG] 병합 후보: {len(combined)}개 (모든 서브쿼리)")
        reranked = self._rerank(query, combined, top_k * 2)

        # 원본 쿼리의 semantic 상위 결과는 앞쪽에 유지
        key = lambda it: f"{it.get('law_name')}::{it.get('article')}"
        must_keep = []
        if all_semantic:
            for s in all_semantic[: min(3, len(all_semantic))]:
                must_keep.append(s)

        ordered = must_keep + reranked
        dedup = {}
        for it in ordered:
            dedup[key(it)] = dedup.get(key(it)) or it
        final = list(dedup.values())

        final = [r for r in final if r.get("similarity", 0) > 0][:top_k]
        if not final:
            final = combined[:top_k]

        for item in final:
            if "similarity" not in item:
                item["similarity"] = item.get("score") or item.get("semantic_score") or 0.0

        if self.wandb_logger:
            search_time = time.time() - search_start
            top_score = final[0].get("score", 0.0) if final else 0.0
            self.wandb_logger.log_search(
                query=query,
                search_time=search_time,
                embedding_time=embedding_time,
                results_count=len(final),
                top_similarity=top_score,
                search_method=f"{search_method}+BM25+rerank(subqueries)",
                deduplication_count=0
            )

        self.last_results = final
        return final

    def _bm25_search_safe(self, query: str, top_k: int) -> List[Dict]:
        """BM25 검색 안전 호출"""
        try:
            return self.bm25.search(query, top_k=top_k)
        except Exception as e:
            print(f"⚠️ BM25 검색 실패: {e}")
            return []

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
                "similarity": item.get("similarity"),
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
                rerank_score = float(score)
                cand["rerank_score"] = rerank_score
                # semantic_score가 있으면 우선 사용, 없으면 rerank 점수 사용
                sim = cand.get("semantic_score")
                if sim is None:
                    sim = rerank_score
                cand["similarity"] = sim
                cand["score"] = sim  # 최종 정렬은 similarity 기준으로

            candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        except Exception as e:
            print(f"⚠️ Rerank 실패, semantic 점수로 정렬합니다: {e}")
            for cand in candidates:
                cand["score"] = cand.get("semantic_score", 0) or cand.get("bm25_score", 0) or 0.0
                cand["similarity"] = cand.get("semantic_score") if cand.get("semantic_score") is not None else cand["score"]
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
