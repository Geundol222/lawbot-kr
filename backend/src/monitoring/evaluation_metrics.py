"""
평가용 메트릭 계산 (실험 비교용)
- Retrieval Metrics: R@k, MRR, NDCG
- Citation Metrics: Precision, Recall, F1
- Answer Quality: Faithfulness, Relevance, Completeness
- Cost & Latency: 토큰 사용량, 응답 시간
"""
import json
import re
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, asdict
import numpy as np


@dataclass
class EvaluationResult:
    """단일 질문에 대한 평가 결과"""
    question_id: str
    question: str

    # Retrieval Metrics
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    mrr: float  # Mean Reciprocal Rank
    ndcg_at_3: float

    # Citation Metrics
    citation_precision: float
    citation_recall: float
    citation_f1: float
    has_citation: bool

    # Answer Quality (LLM-based)
    faithfulness: float  # 검색 결과 기반 답변 여부 (0-1)
    relevance: float     # 질문과의 관련성 (0-1)
    completeness: float  # 답변 완성도 (0-1)

    # Cost & Latency
    response_time_ms: int
    total_tokens: int
    api_calls: int
    search_iterations: int

    # Mode
    mode: str  # "vanilla", "current", "full_self_rag"

    def to_dict(self):
        """WandB 로깅용 딕셔너리 변환"""
        return asdict(self)


class EvaluationMetrics:
    """평가 메트릭 계산 클래스"""

    @staticmethod
    def normalize_article_name(article_str: str) -> str:
        """
        법령 조문 이름 정규화

        예:
            "민법 제750조" → "민법 750"
            "근로기준법 제56조" → "근로기준법 56"
            "민법 750" → "민법 750" (변경 없음)

        Returns:
            정규화된 문자열 (법령명 + 공백 + 숫자)
        """
        # "제"와 "조" 제거, 공백 정리
        normalized = article_str.replace("제", "").replace("조", "").strip()
        # 연속된 공백을 하나로
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    @staticmethod
    def calculate_recall_at_k(
        retrieved_docs: List[Dict[str, Any]],
        ground_truth_articles: List[str],
        k: int
    ) -> float:
        """
        Recall@k 계산

        Args:
            retrieved_docs: 검색된 문서 리스트 [{"law_name": "민법", "article": "750"}, ...]
            ground_truth_articles: 정답 조문 리스트 ["민법 750", "민법 751", ...]
            k: 상위 k개 문서

        Returns:
            Recall@k (0-1)
        """
        if not ground_truth_articles:
            return 1.0  # 정답이 없으면 perfect score

        # 상위 k개 문서에서 법령명 + 조문 추출 (정규화)
        retrieved_set = set()
        for doc in retrieved_docs[:k]:
            law_article = f"{doc.get('law_name', '')} {doc.get('article', '')}".strip()
            normalized = EvaluationMetrics.normalize_article_name(law_article)
            retrieved_set.add(normalized)

        # Ground Truth 정규화
        ground_truth_set = set(
            EvaluationMetrics.normalize_article_name(article)
            for article in ground_truth_articles
        )
        matched = len(retrieved_set.intersection(ground_truth_set))

        return matched / len(ground_truth_set)

    @staticmethod
    def calculate_mrr(
        retrieved_docs: List[Dict[str, Any]],
        ground_truth_articles: List[str]
    ) -> float:
        """
        Mean Reciprocal Rank 계산

        Returns:
            MRR (0-1): 첫 번째 정답 문서의 역순위 평균
        """
        if not ground_truth_articles:
            return 1.0

        ground_truth_set = set(
            EvaluationMetrics.normalize_article_name(article)
            for article in ground_truth_articles
        )

        for rank, doc in enumerate(retrieved_docs, start=1):
            law_article = f"{doc.get('law_name', '')} {doc.get('article', '')}".strip()
            normalized = EvaluationMetrics.normalize_article_name(law_article)
            if normalized in ground_truth_set:
                return 1.0 / rank

        return 0.0  # 정답 문서를 찾지 못함

    @staticmethod
    def calculate_ndcg_at_k(
        retrieved_docs: List[Dict[str, Any]],
        ground_truth_articles: List[str],
        k: int
    ) -> float:
        """
        Normalized Discounted Cumulative Gain@k 계산

        Returns:
            NDCG@k (0-1): 정답 순위를 고려한 검색 품질
        """
        if not ground_truth_articles:
            return 1.0

        ground_truth_set = set(
            EvaluationMetrics.normalize_article_name(article)
            for article in ground_truth_articles
        )

        # DCG 계산
        dcg = 0.0
        for i, doc in enumerate(retrieved_docs[:k], start=1):
            law_article = f"{doc.get('law_name', '')} {doc.get('article', '')}".strip()
            normalized = EvaluationMetrics.normalize_article_name(law_article)
            relevance = 1 if normalized in ground_truth_set else 0
            dcg += relevance / np.log2(i + 1)

        # IDCG 계산 (이상적인 순서)
        idcg = sum(1.0 / np.log2(i + 1) for i in range(1, min(len(ground_truth_articles), k) + 1))

        return dcg / idcg if idcg > 0 else 0.0

    @staticmethod
    def extract_citations_from_answer(answer: str) -> Set[str]:
        """
        답변에서 인용된 법령 추출

        예: "민법 제750조", "근로기준법 제56조" → {"민법 750", "근로기준법 56"}

        Returns:
            Set of "법령명 조문번호"
        """
        citations = set()

        # 패턴 1: "법령명 제XXX조"
        pattern1 = r'([가-힣]+(?:법|령|규칙|조례))\s*제\s*(\d+)조'
        matches1 = re.findall(pattern1, answer)
        for law_name, article in matches1:
            citations.add(f"{law_name} {article}")

        # 패턴 2: "법령명 XXX조" (제 없이)
        pattern2 = r'([가-힣]+(?:법|령|규칙|조례))\s*(\d+)조'
        matches2 = re.findall(pattern2, answer)
        for law_name, article in matches2:
            citations.add(f"{law_name} {article}")

        return citations

    @staticmethod
    def calculate_citation_metrics(
        answer: str,
        ground_truth_articles: List[str]
    ) -> Dict[str, float]:
        """
        Citation Precision, Recall, F1 계산

        Args:
            answer: LLM 생성 답변
            ground_truth_articles: 정답 조문 리스트

        Returns:
            {
                "precision": 0-1,
                "recall": 0-1,
                "f1": 0-1,
                "has_citation": bool
            }
        """
        citations = EvaluationMetrics.extract_citations_from_answer(answer)
        # 정규화
        citations_normalized = set(
            EvaluationMetrics.normalize_article_name(c) for c in citations
        )
        ground_truth_set = set(
            EvaluationMetrics.normalize_article_name(article)
            for article in ground_truth_articles
        )

        if not citations:
            return {
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "has_citation": False
            }

        # Precision: 인용한 법령 중 정답 비율
        true_positives = len(citations_normalized.intersection(ground_truth_set))
        precision = true_positives / len(citations_normalized) if citations_normalized else 0.0

        # Recall: 정답 법령 중 인용한 비율
        recall = true_positives / len(ground_truth_set) if ground_truth_set else 0.0

        # F1
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "has_citation": True
        }

    @staticmethod
    def calculate_answer_quality_llm(
        question: str,
        answer: str,
        retrieved_context: str,
        llm
    ) -> Dict[str, float]:
        """
        LLM 기반 답변 품질 평가

        Args:
            question: 사용자 질문
            answer: LLM 생성 답변
            retrieved_context: 검색된 법령 정보
            llm: LLM 인스턴스 (Gemini Flash Lite 권장)

        Returns:
            {
                "faithfulness": 0-1,    # 검색 결과 충실도
                "relevance": 0-1,       # 질문 관련성
                "completeness": 0-1     # 답변 완성도
            }
        """
        from src.config import llm_invoke_with_retry

        eval_prompt = f"""다음 답변의 품질을 평가하세요.

**질문:**
{question}

**검색된 법령 정보:**
{retrieved_context[:1000]}

**생성된 답변:**
{answer}

**평가 기준:**
1. Faithfulness (충실도): 답변이 검색된 법령 정보에만 기반했는가? (0.0-1.0)
   - 1.0: 검색 결과만 사용
   - 0.5: 일부 외부 지식 사용
   - 0.0: 검색 결과 무시

2. Relevance (관련성): 답변이 질문과 얼마나 관련되는가? (0.0-1.0)
   - 1.0: 질문에 정확히 답변
   - 0.5: 부분적으로 관련
   - 0.0: 무관한 답변

3. Completeness (완성도): 답변이 충분히 완전한가? (0.0-1.0)
   - 1.0: 모든 정보 포함
   - 0.5: 일부 정보 누락
   - 0.0: 거의 답변 없음

JSON 형식으로만 답변:
{{
    "faithfulness": 0.0-1.0,
    "relevance": 0.0-1.0,
    "completeness": 0.0-1.0
}}"""

        try:
            response = llm_invoke_with_retry(llm, eval_prompt)
            content = response.content if hasattr(response, 'content') else str(response)

            # JSON 추출 (마크다운 코드블록 제거)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)

            return {
                "faithfulness": float(result.get("faithfulness", 0.5)),
                "relevance": float(result.get("relevance", 0.5)),
                "completeness": float(result.get("completeness", 0.5))
            }

        except Exception as e:
            print(f"⚠️ LLM 평가 실패: {e}")
            return {
                "faithfulness": 0.5,
                "relevance": 0.5,
                "completeness": 0.5
            }

    @staticmethod
    def calculate_all_metrics(
        question_id: str,
        question: str,
        answer: str,
        retrieved_docs: List[Dict[str, Any]],
        ground_truth: Dict[str, Any],
        response_time_ms: int,
        total_tokens: int,
        api_calls: int,
        search_iterations: int,
        mode: str,
        llm=None
    ) -> EvaluationResult:
        """
        모든 평가 메트릭 계산

        Args:
            question_id: 질문 ID
            question: 사용자 질문
            answer: LLM 생성 답변
            retrieved_docs: 검색된 문서 리스트
            ground_truth: 정답 데이터 {"articles": ["민법 750", ...], "context": "..."}
            response_time_ms: 응답 시간 (ms)
            total_tokens: 총 토큰 수
            api_calls: API 호출 횟수
            search_iterations: 검색 반복 횟수
            mode: "vanilla", "current", "full_self_rag"
            llm: LLM 인스턴스 (품질 평가용)

        Returns:
            EvaluationResult
        """
        ground_truth_articles = ground_truth.get("articles", [])
        ground_truth_context = ground_truth.get("context", "")

        # Retrieval Metrics
        recall_at_3 = EvaluationMetrics.calculate_recall_at_k(retrieved_docs, ground_truth_articles, k=3)
        recall_at_5 = EvaluationMetrics.calculate_recall_at_k(retrieved_docs, ground_truth_articles, k=5)
        recall_at_10 = EvaluationMetrics.calculate_recall_at_k(retrieved_docs, ground_truth_articles, k=10)
        mrr = EvaluationMetrics.calculate_mrr(retrieved_docs, ground_truth_articles)
        ndcg_at_3 = EvaluationMetrics.calculate_ndcg_at_k(retrieved_docs, ground_truth_articles, k=3)

        # Citation Metrics
        citation_metrics = EvaluationMetrics.calculate_citation_metrics(answer, ground_truth_articles)

        # Answer Quality (LLM 기반)
        if llm:
            retrieved_context = "\n\n".join([
                f"법령: {doc.get('law_name', '')} {doc.get('article', '')}\n내용: {doc.get('content', '')[:200]}"
                for doc in retrieved_docs[:3]
            ])
            quality_metrics = EvaluationMetrics.calculate_answer_quality_llm(
                question, answer, retrieved_context, llm
            )
        else:
            quality_metrics = {
                "faithfulness": 0.5,
                "relevance": 0.5,
                "completeness": 0.5
            }

        return EvaluationResult(
            question_id=question_id,
            question=question,

            # Retrieval
            recall_at_3=recall_at_3,
            recall_at_5=recall_at_5,
            recall_at_10=recall_at_10,
            mrr=mrr,
            ndcg_at_3=ndcg_at_3,

            # Citation
            citation_precision=citation_metrics["precision"],
            citation_recall=citation_metrics["recall"],
            citation_f1=citation_metrics["f1"],
            has_citation=citation_metrics["has_citation"],

            # Quality
            faithfulness=quality_metrics["faithfulness"],
            relevance=quality_metrics["relevance"],
            completeness=quality_metrics["completeness"],

            # Cost & Latency
            response_time_ms=response_time_ms,
            total_tokens=total_tokens,
            api_calls=api_calls,
            search_iterations=search_iterations,

            # Mode
            mode=mode
        )


class ExperimentLogger:
    """실험 결과 로깅 (WandB 연동)"""

    def __init__(self, wandb_logger):
        self.wandb_logger = wandb_logger
        self.results = []

    def log_evaluation(self, eval_result: EvaluationResult):
        """단일 평가 결과 로깅"""
        # 개별 쿼리 메트릭 로깅
        metrics = eval_result.to_dict()

        # mode별 prefix 추가
        mode = metrics.pop("mode")
        question_id = metrics.pop("question_id")
        question = metrics.pop("question")

        # WandB에 로깅
        prefixed_metrics = {
            f"eval/{mode}/{k}": v for k, v in metrics.items()
            if isinstance(v, (int, float, bool))
        }

        self.wandb_logger.log_metrics(prefixed_metrics)

        # 결과 저장
        self.results.append(eval_result)

    def log_aggregate_metrics(self):
        """집계 메트릭 로깅 (전체 평균)"""
        if not self.results:
            return

        # Mode별 그룹화
        mode_results = {}
        for result in self.results:
            mode = result.mode
            if mode not in mode_results:
                mode_results[mode] = []
            mode_results[mode].append(result)

        # Mode별 평균 계산
        for mode, results in mode_results.items():
            n = len(results)

            avg_metrics = {
                f"eval_summary/{mode}/avg_recall_at_3": np.mean([r.recall_at_3 for r in results]),
                f"eval_summary/{mode}/avg_recall_at_5": np.mean([r.recall_at_5 for r in results]),
                f"eval_summary/{mode}/avg_recall_at_10": np.mean([r.recall_at_10 for r in results]),
                f"eval_summary/{mode}/avg_mrr": np.mean([r.mrr for r in results]),
                f"eval_summary/{mode}/avg_ndcg_at_3": np.mean([r.ndcg_at_3 for r in results]),

                f"eval_summary/{mode}/avg_citation_precision": np.mean([r.citation_precision for r in results]),
                f"eval_summary/{mode}/avg_citation_recall": np.mean([r.citation_recall for r in results]),
                f"eval_summary/{mode}/avg_citation_f1": np.mean([r.citation_f1 for r in results]),
                f"eval_summary/{mode}/citation_rate": sum([r.has_citation for r in results]) / n,

                f"eval_summary/{mode}/avg_faithfulness": np.mean([r.faithfulness for r in results]),
                f"eval_summary/{mode}/avg_relevance": np.mean([r.relevance for r in results]),
                f"eval_summary/{mode}/avg_completeness": np.mean([r.completeness for r in results]),

                f"eval_summary/{mode}/avg_response_time_ms": np.mean([r.response_time_ms for r in results]),
                f"eval_summary/{mode}/avg_total_tokens": np.mean([r.total_tokens for r in results]),
                f"eval_summary/{mode}/avg_api_calls": np.mean([r.api_calls for r in results]),
                f"eval_summary/{mode}/avg_search_iterations": np.mean([r.search_iterations for r in results]),

                f"eval_summary/{mode}/count": n
            }

            # WandB Summary에 저장 (최종 메트릭)
            if self.wandb_logger.enabled and self.wandb_logger.run:
                for key, value in avg_metrics.items():
                    self.wandb_logger.run.summary[key] = value

            print(f"\n✅ {mode} 평균 메트릭:")
            print(f"   Recall@3: {avg_metrics[f'eval_summary/{mode}/avg_recall_at_3']:.3f}")
            print(f"   Recall@5: {avg_metrics[f'eval_summary/{mode}/avg_recall_at_5']:.3f}")
            print(f"   Recall@10: {avg_metrics[f'eval_summary/{mode}/avg_recall_at_10']:.3f}")
            print(f"   MRR: {avg_metrics[f'eval_summary/{mode}/avg_mrr']:.3f}")
            print(f"   Citation F1: {avg_metrics[f'eval_summary/{mode}/avg_citation_f1']:.3f}")
            print(f"   Faithfulness: {avg_metrics[f'eval_summary/{mode}/avg_faithfulness']:.3f}")
            print(f"   Avg Response Time: {avg_metrics[f'eval_summary/{mode}/avg_response_time_ms']:.0f}ms")

    def log_comparison_table(self):
        """Mode 비교 테이블 로깅"""
        if not self.results:
            return

        # Mode별 집계
        mode_stats = {}
        for result in self.results:
            mode = result.mode
            if mode not in mode_stats:
                mode_stats[mode] = []
            mode_stats[mode].append(result)

        # 테이블 데이터 생성
        table_data = []
        for mode, results in mode_stats.items():
            table_data.append([
                mode,
                np.mean([r.recall_at_3 for r in results]),
                np.mean([r.mrr for r in results]),
                np.mean([r.citation_f1 for r in results]),
                np.mean([r.faithfulness for r in results]),
                np.mean([r.response_time_ms for r in results]),
                np.mean([r.total_tokens for r in results]),
                len(results)
            ])

        # WandB 테이블 로깅
        self.wandb_logger.log_table(
            "mode_comparison",
            ["Mode", "Recall@3", "MRR", "Citation F1", "Faithfulness", "Avg Response Time (ms)", "Avg Tokens", "Count"],
            table_data
        )
