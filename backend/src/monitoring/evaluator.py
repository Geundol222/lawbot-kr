"""
오프라인 평가 실행기
- 평가 데이터셋으로 배치 실행
- Mode별 성능 비교
- WandB에 결과 로깅
"""
import json
import time
from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm

from src.agentic_rag import AgenticRAG
from src.config import get_llm
from src.monitoring.wandb_logger import WandbLogger
from src.monitoring.evaluation_metrics import EvaluationMetrics, ExperimentLogger


class OfflineEvaluator:
    """오프라인 평가 실행기"""

    def __init__(
        self,
        eval_dataset_path: str,
        ground_truth_path: str,
        mode: str = "current",
        wandb_project: str = "lawbot-kr-evaluation",
        wandb_experiment: str = None
    ):
        """
        Args:
            eval_dataset_path: 평가 질문 데이터셋 경로 (JSON)
            ground_truth_path: Ground Truth 데이터 경로 (JSON)
            mode: "vanilla", "current", "full_self_rag"
            wandb_project: WandB 프로젝트 이름
            wandb_experiment: 실험명 (예: "baseline_v1", "self_rag_v2")
        """
        self.eval_dataset_path = Path(eval_dataset_path)
        self.ground_truth_path = Path(ground_truth_path)
        self.mode = mode
        self.wandb_project = wandb_project
        self.wandb_experiment = wandb_experiment or f"{mode}_evaluation"

        # 데이터 로드
        self.eval_questions = self._load_json(self.eval_dataset_path)
        self.ground_truth = self._load_json(self.ground_truth_path)

        # AgenticRAG 초기화
        self.agent = AgenticRAG(mode=mode)

        # LLM for evaluation
        self.eval_llm = get_llm("flash-lite")

        # WandB 초기화
        self.wandb_logger = WandbLogger(
            project_name=wandb_project,
            enabled=True,
            run_name=f"{mode}_{time.strftime('%Y%m%d_%H%M%S')}",
            tags=[mode, self.wandb_experiment],
            group=f"eval_{time.strftime('%Y%m%d')}"
        )

        # Experiment Logger
        self.exp_logger = ExperimentLogger(self.wandb_logger)

    def _load_json(self, path: Path) -> Dict:
        """JSON 파일 로드"""
        if not path.exists():
            raise FileNotFoundError(f"파일이 없습니다: {path}")

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def run_evaluation(self) -> Dict[str, Any]:
        """
        평가 실행

        Returns:
            집계 메트릭 딕셔너리
        """
        print(f"\n{'='*60}")
        print(f"🧪 오프라인 평가 시작: {self.mode}")
        print(f"{'='*60}")
        print(f"질문 수: {len(self.eval_questions)}")
        print(f"WandB Run: {self.wandb_logger.run.name if self.wandb_logger.run else 'Disabled'}")
        print(f"{'='*60}\n")

        results = []

        for question_data in tqdm(self.eval_questions, desc=f"[{self.mode}] 평가 중"):
            question_id = question_data["id"]
            question = question_data["question"]

            # Ground Truth 가져오기
            gt = self.ground_truth.get(question_id, {})
            if not gt:
                print(f"⚠️ Ground Truth 없음: {question_id}")
                continue

            try:
                # Agent 실행
                start_time = time.time()
                answer, retrieved_docs, metrics = self._run_agent_with_metrics(question, gt)
                response_time_ms = int((time.time() - start_time) * 1000)

                # 평가 메트릭 계산
                eval_result = EvaluationMetrics.calculate_all_metrics(
                    question_id=question_id,
                    question=question,
                    answer=answer,
                    retrieved_docs=retrieved_docs,
                    ground_truth=gt,
                    response_time_ms=response_time_ms,
                    total_tokens=metrics.get("total_tokens", 0),
                    api_calls=metrics.get("api_calls", 0),
                    search_iterations=metrics.get("search_iterations", 1),
                    mode=self.mode,
                    llm=self.eval_llm
                )

                # WandB 로깅
                self.exp_logger.log_evaluation(eval_result)

                results.append(eval_result)

                print(f"✅ {question_id}: Recall@3={eval_result.recall_at_3:.2f}, F1={eval_result.citation_f1:.2f}")

            except Exception as e:
                print(f"❌ {question_id} 실패: {e}")
                import traceback
                traceback.print_exc()

        # 집계 메트릭 계산 및 로깅
        self.exp_logger.log_aggregate_metrics()

        # 비교 테이블 로깅
        self.exp_logger.log_comparison_table()

        # WandB 종료
        self.wandb_logger.finish()

        print(f"\n{'='*60}")
        print(f"✅ 평가 완료: {len(results)}/{len(self.eval_questions)}")
        print(f"{'='*60}\n")

        return {
            "mode": self.mode,
            "total_questions": len(self.eval_questions),
            "successful_evaluations": len(results),
            "results": results
        }

    def _run_agent_with_metrics(self, question: str, ground_truth: Dict[str, Any]) -> tuple:
        """
        Agent 실행 및 메트릭 수집

        Args:
            question: 사용자 질문
            ground_truth: Ground Truth 데이터 (retrieved_docs 포함 가능)

        Returns:
            (answer, retrieved_docs, metrics)
        """
        # Ground Truth에 retrieved_docs가 있으면 사용 (재현성 확보)
        if "retrieved_docs" in ground_truth and ground_truth["retrieved_docs"]:
            print(f"  [재현성 모드] Ground Truth의 고정된 검색 결과 사용 ({len(ground_truth['retrieved_docs'])}개)")
            retrieved_docs = ground_truth["retrieved_docs"]

            # TODO: AgenticRAG.run_with_fixed_context() 구현 필요 (추후)
            # 현재는 일반 run_with_metrics() 사용 (실시간 검색)
            result = self.agent.run_with_metrics(question)
            answer = result["answer"]
            # retrieved_docs는 GT 것을 사용 (재현성 위해)

        else:
            # Ground Truth에 retrieved_docs 없으면 실제 검색 수행
            print(f"  [일반 모드] 실시간 검색 수행 (mode: {self.mode})")

            # run_with_metrics() 사용
            result = self.agent.run_with_metrics(question)
            answer = result["answer"]
            retrieved_docs = result["retrieved_docs"]

        metrics = result.get("metrics", {
            "total_tokens": 0,
            "api_calls": 0,
            "search_iterations": 1
        })

        return answer, retrieved_docs, metrics


def run_comparison_experiment(
    eval_dataset_path: str,
    ground_truth_path: str,
    modes: List[str] = ["vanilla", "current", "full_self_rag"]
):
    """
    여러 Mode 비교 실험 실행

    Args:
        eval_dataset_path: 평가 질문 데이터셋 경로
        ground_truth_path: Ground Truth 경로
        modes: 비교할 모드 리스트
    """
    print("\n🔬 비교 실험 시작")
    print(f"비교 모드: {', '.join(modes)}\n")

    all_results = {}

    for mode in modes:
        evaluator = OfflineEvaluator(
            eval_dataset_path=eval_dataset_path,
            ground_truth_path=ground_truth_path,
            mode=mode,
            wandb_project="lawbot-kr-comparison",
            wandb_experiment=f"comparison_{time.strftime('%Y%m%d')}"
        )

        results = evaluator.run_evaluation()
        all_results[mode] = results

    print("\n" + "="*60)
    print("🎉 전체 비교 실험 완료!")
    print("="*60)

    for mode, results in all_results.items():
        print(f"\n{mode}:")
        print(f"  - 성공: {results['successful_evaluations']}/{results['total_questions']}")

    return all_results


if __name__ == "__main__":
    # 단일 모드 평가 예시
    evaluator = OfflineEvaluator(
        eval_dataset_path="datasets/eval_questions.json",
        ground_truth_path="datasets/ground_truth.json",
        mode="current",
        wandb_experiment="baseline_test"
    )

    evaluator.run_evaluation()

    # 비교 실험 예시
    # run_comparison_experiment(
    #     eval_dataset_path="datasets/eval_questions.json",
    #     ground_truth_path="datasets/ground_truth.json",
    #     modes=["vanilla", "current"]
    # )
