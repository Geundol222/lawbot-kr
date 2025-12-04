from sentence_transformers import SentenceTransformer
from supabase import create_client
import numpy as np

from src.config import SUPABASE_URL, SUPABASE_KEY

class VectorSearch:
    def __init__(self):
        # sentence-transformers 올바른 클래스명 사용
        self.model = SentenceTransformer("intfloat/multilingual-e5-large-instruct")
        # create_client는 (url, key) 순서를 사용
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    def search(self, query: str, top_k: int = 5, threshold: float = 0.0):
        """유사한 법령 검색

        Args:
            query: 검색 질문
            top_k: 반환할 최대 결과 수
            threshold: 유사도 임계값 (이 값 이상만 반환)
        """
        # 질문 임베딩
        query_emb = np.array(self.model.encode(query), dtype=np.float32).tolist()

        # Supabase RPC 함수 호출 (match_law_documents)
        try:
            result = self.supabase.rpc(
                'match_law_documents',
                {
                    'query_embedding': query_emb,
                    'match_threshold': threshold,
                    'match_count': top_k
                }
            ).execute()

            if result.data:
                return result.data

        except Exception as e:
            print(f"⚠️ RPC 호출 실패, 폴백 방식 사용: {e}")

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

        # 정렬 & 반환
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        return similarities[:top_k]
