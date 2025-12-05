from sentence_transformers import SentenceTransformer
from supabase import create_client
import numpy as np
import time

from src.config import SUPABASE_URL, SUPABASE_KEY
from src.monitoring import get_wandb_logger, VectorSearchLogger

class VectorSearch:
    def __init__(self):
        # sentence-transformers 올바른 클래스명 사용
        self.model = SentenceTransformer("intfloat/multilingual-e5-large-instruct")
        # create_client는 (url, key) 순서를 사용
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        # WandB 로거 초기화
        try:
            self.wandb_logger = VectorSearchLogger(get_wandb_logger())
        except Exception:
            self.wandb_logger = None

    def search(self, query: str, top_k: int = 5, threshold: float = 0.0):
        """유사한 법령 검색

        Args:
            query: 검색 질문
            top_k: 반환할 최대 결과 수
            threshold: 유사도 임계값 (이 값 이상만 반환)
        """
        search_start = time.time()

        # 질문 임베딩
        embedding_start = time.time()
        query_emb = np.array(self.model.encode(query), dtype=np.float32).tolist()
        embedding_time = time.time() - embedding_start

        search_method = "RPC"

        # Supabase RPC 함수 호출 (match_law_documents)
        try:
            result = self.supabase.rpc(
                'match_law_documents',
                {
                    'query_embedding': query_emb,
                    'match_threshold': threshold,
                    'match_count': top_k * 3  # 청크 중복 고려하여 더 많이 가져옴
                }
            ).execute()

            if result.data:
                before_dedup = len(result.data)
                final_results = self._deduplicate_chunks(result.data, top_k)
                dedup_count = before_dedup - len(final_results)

                # WandB 로깅
                if self.wandb_logger:
                    search_time = time.time() - search_start
                    top_similarity = final_results[0].get("similarity", 0.0) if final_results else 0.0
                    self.wandb_logger.log_search(
                        query=query,
                        search_time=search_time,
                        embedding_time=embedding_time,
                        results_count=len(final_results),
                        top_similarity=top_similarity,
                        search_method=search_method,
                        deduplication_count=dedup_count
                    )

                return final_results

        except Exception as e:
            print(f"⚠️ RPC 호출 실패, 폴백 방식 사용: {e}")
            search_method = "Fallback"

        # 폴백: 수동 유사도 계산
        query_emb = np.array(query_emb, dtype=np.float32)

        result = (
            self.supabase.table("law_cache")
            .select("*")
            .execute()
        )

        # 유사도 계산
        similarities = []
        for row in result.data:
            emb_raw = row.get("embedding")

            # Supabase에서 문자열/리스트 모두 들어올 수 있으니 안전하게 float array로 변환
            try:
                if isinstance(emb_raw, str):
                    import json
                    emb_raw = json.loads(emb_raw)
                law_emb = np.array(emb_raw, dtype=np.float32)
            except Exception:
                continue  # 잘못된 임베딩 레코드는 건너뛴다

            if law_emb.size == 0:
                continue

            # 코사인 유사도
            sim = float(
                np.dot(law_emb, query_emb)
                / (np.linalg.norm(law_emb) * np.linalg.norm(query_emb))
            )

            if sim >= threshold:
                similarities.append(
                    {
                        "law_name": row.get("law_name"),
                        "article": row.get("article"),
                        "mst": row.get("mst"),  # 법령일련번호 연결
                        "content": row.get("content"),
                        "similarity": sim,
                    }
                )

        # 정렬
        similarities.sort(key=lambda x: x['similarity'], reverse=True)

        # 청크 중복 제거 후 반환
        before_dedup = len(similarities)
        final_results = self._deduplicate_chunks(similarities, top_k)
        dedup_count = before_dedup - len(final_results)

        # WandB 로깅
        if self.wandb_logger:
            search_time = time.time() - search_start
            top_similarity = final_results[0].get("similarity", 0.0) if final_results else 0.0
            self.wandb_logger.log_search(
                query=query,
                search_time=search_time,
                embedding_time=embedding_time,
                results_count=len(final_results),
                top_similarity=top_similarity,
                search_method=search_method,
                deduplication_count=dedup_count
            )

        return final_results

    def _deduplicate_chunks(self, results: list, top_k: int) -> list:
        """
        청크 중복 제거 (같은 조문의 여러 part 중 가장 높은 유사도만 유지)

        Args:
            results: 검색 결과 리스트
            top_k: 반환할 최대 결과 수

        Returns:
            중복 제거된 결과
        """
        seen_articles = {}

        for item in results:
            law_name = item.get("law_name")
            article = item.get("article", "")

            # 청크 suffix 제거 (예: "제56조_part1" -> "제56조")
            base_article = article.split("_part")[0]
            key = f"{law_name}:{base_article}"

            # 같은 조문이 없거나, 더 높은 유사도면 업데이트
            if key not in seen_articles or item.get("similarity", 0) > seen_articles[key].get("similarity", 0):
                # article 필드를 base로 정규화
                normalized_item = item.copy()
                normalized_item["article"] = base_article
                seen_articles[key] = normalized_item

        # 유사도 순으로 정렬하여 반환
        deduplicated = list(seen_articles.values())
        deduplicated.sort(key=lambda x: x.get("similarity", 0), reverse=True)

        return deduplicated[:top_k]
