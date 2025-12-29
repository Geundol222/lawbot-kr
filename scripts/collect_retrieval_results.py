"""
검색 결과 수집 스크립트

평가 데이터셋의 모든 질문에 대해 검색 결과를 수집하고
Ground Truth에 `retrieved_docs` 필드로 저장합니다.

목적:
1. 재현성 확보: 매번 같은 검색 결과 사용
2. 공정한 비교: Vanilla vs Self-RAG 차이를 순수하게 생성 능력만 비교
3. 실험 시간 단축: 검색 건너뛰고 바로 생성

사용법:
    python scripts/collect_retrieval_results.py --eval_questions datasets/eval_questions.json --ground_truth datasets/ground_truth.json
"""

import json
import sys
from pathlib import Path
from tqdm import tqdm
import argparse

# backend 경로 추가
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from src.embeddings.vector_search import VectorSearch


def collect_retrieval_results(
    eval_questions_path: str,
    ground_truth_path: str,
    top_k: int = 5,
    deterministic: bool = True
):
    """
    평가 데이터셋의 모든 질문에 대해 검색 결과 수집

    Args:
        eval_questions_path: 평가 질문 JSON 경로
        ground_truth_path: Ground Truth JSON 경로 (업데이트됨)
        top_k: 검색할 문서 수
        deterministic: 결정적 검색 모드 (서브쿼리 순서 고정)
    """
    print(f"\n{'='*60}")
    print(f"🔍 검색 결과 수집 시작")
    print(f"{'='*60}\n")

    # 평가 질문 로드
    with open(eval_questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    # Ground Truth 로드 (없으면 빈 dict)
    gt_path = Path(ground_truth_path)
    if gt_path.exists():
        with open(ground_truth_path, "r", encoding="utf-8") as f:
            ground_truth = json.load(f)
    else:
        ground_truth = {}

    # VectorSearch 초기화
    print("📦 VectorSearch 초기화 중...")
    vector_search = VectorSearch()

    print(f"✅ 총 {len(questions)}개 질문에 대해 검색 결과 수집\n")

    # 각 질문마다 검색 실행
    collected_count = 0
    skipped_count = 0

    for question_data in tqdm(questions, desc="검색 중"):
        qid = question_data["id"]
        question = question_data["question"]

        # 이미 retrieved_docs가 있으면 건너뛰기 (선택)
        if qid in ground_truth and "retrieved_docs" in ground_truth[qid]:
            print(f"⏭️  {qid}: 이미 검색 결과 존재 (건너뜀)")
            skipped_count += 1
            continue

        # 검색 실행
        try:
            results = vector_search.search(question, top_k=top_k)

            # Ground Truth에 추가
            if qid not in ground_truth:
                ground_truth[qid] = {}

            # 검색 결과를 직렬화 가능한 형태로 변환
            serializable_results = []
            for result in results:
                serializable_results.append({
                    "law_name": result.get("law_name", ""),
                    "article": result.get("article", ""),
                    "content": result.get("content", ""),
                    "similarity": float(result.get("similarity", 0.0)),
                    "score": float(result.get("score", 0.0))
                })

            ground_truth[qid]["retrieved_docs"] = serializable_results

            collected_count += 1

            print(f"✅ {qid}: {len(results)}개 문서 수집")
            if results:
                print(f"   Top 1: {results[0].get('law_name')} {results[0].get('article')} (유사도: {results[0].get('similarity', 0):.3f})")

        except Exception as e:
            print(f"❌ {qid} 검색 실패: {e}")
            import traceback
            traceback.print_exc()

    # Ground Truth 저장
    print(f"\n💾 Ground Truth 저장 중: {ground_truth_path}")
    with open(ground_truth_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ 검색 결과 수집 완료!")
    print(f"{'='*60}")
    print(f"수집 완료: {collected_count}개")
    print(f"건너뜀: {skipped_count}개")
    print(f"총 {collected_count + skipped_count}개 질문\n")


def verify_retrieval_results(ground_truth_path: str):
    """
    수집된 검색 결과 검증

    Args:
        ground_truth_path: Ground Truth JSON 경로
    """
    print(f"\n{'='*60}")
    print(f"🔍 검색 결과 검증")
    print(f"{'='*60}\n")

    with open(ground_truth_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    total = len(ground_truth)
    with_retrieved = 0
    empty_retrieved = 0

    for qid, gt in ground_truth.items():
        if "retrieved_docs" in gt:
            with_retrieved += 1
            if not gt["retrieved_docs"]:
                empty_retrieved += 1
                print(f"⚠️  {qid}: 검색 결과 없음")

    print(f"총 질문: {total}개")
    print(f"검색 결과 있음: {with_retrieved}개")
    print(f"검색 결과 없음 (빈 리스트): {empty_retrieved}개")
    print(f"검색 결과 미수집: {total - with_retrieved}개\n")

    if empty_retrieved > 0:
        print(f"⚠️  경고: {empty_retrieved}개 질문의 검색 결과가 비어있습니다.")
        print("   threshold를 낮추거나 질문을 수정하세요.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="검색 결과 수집")
    parser.add_argument(
        "--eval_questions",
        type=str,
        default="datasets/eval_questions.json",
        help="평가 질문 JSON 경로"
    )
    parser.add_argument(
        "--ground_truth",
        type=str,
        default="datasets/ground_truth.json",
        help="Ground Truth JSON 경로"
    )
    parser.add_argument(
        "--top_k",
        type=int,
        default=5,
        help="검색할 문서 수"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="검색 결과 검증만 수행"
    )

    args = parser.parse_args()

    if args.verify:
        # 검증만 수행
        verify_retrieval_results(args.ground_truth)
    else:
        # 수집 실행
        collect_retrieval_results(
            eval_questions_path=args.eval_questions,
            ground_truth_path=args.ground_truth,
            top_k=args.top_k
        )

        # 수집 후 자동 검증
        verify_retrieval_results(args.ground_truth)
