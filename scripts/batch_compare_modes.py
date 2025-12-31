"""
배치 모드 비교 실험 스크립트
- eval_questions.json의 모든 질문에 대해 3가지 모드(vanilla, current, self_rag) 비교
- 결과를 JSON 파일로 저장하여 분석 가능
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import json
import time
from datetime import datetime
from src.agentic_rag import AgenticRAG


def run_batch_experiment(output_file: str = None):
    """배치 실험 실행"""

    # 질문 로드
    questions_file = os.path.join(os.path.dirname(__file__), '..', 'datasets', 'eval_questions.json')
    with open(questions_file, 'r', encoding='utf-8') as f:
        questions = json.load(f)

    modes = ["vanilla", "current", "self_rag"]
    results = []

    print(f"\n{'='*80}")
    print(f"📊 배치 실험 시작: {len(questions)}개 질문 × {len(modes)}개 모드 = {len(questions) * len(modes)}회 실행")
    print(f"{'='*80}\n")

    for idx, q_item in enumerate(questions, 1):
        question_id = q_item['id']
        question = q_item['question']
        category = q_item.get('category', 'unknown')
        difficulty = q_item.get('difficulty', 'unknown')

        print(f"\n[{idx}/{len(questions)}] 질문: {question}")
        print(f"   카테고리: {category} | 난이도: {difficulty}")
        print(f"   {'='*70}")

        question_results = {
            "question_id": question_id,
            "question": question,
            "category": category,
            "difficulty": difficulty,
            "modes": {}
        }

        for mode in modes:
            print(f"\n   🔧 모드: {mode.upper()}")
            try:
                agent = AgenticRAG(mode=mode)
                result = agent.run_with_metrics(question)

                # 메트릭 추출
                metrics = result.get('metrics', {})
                answer = result.get('answer', '')

                # 답변 길이 계산
                answer_length = len(answer)

                question_results['modes'][mode] = {
                    "answer": answer,
                    "answer_length": answer_length,
                    "response_time_ms": metrics.get('response_time_ms', 0),
                    "total_tokens": metrics.get('total_tokens', 0),
                    "api_calls": metrics.get('api_calls', 0),
                    "search_iterations": metrics.get('search_iterations', 0),
                    "retrieved_docs_count": len(result.get('retrieved_docs', []))
                }

                print(f"      ⏱️  응답시간: {metrics.get('response_time_ms', 0)}ms")
                print(f"      💰 토큰: {metrics.get('total_tokens', 0)}")
                print(f"      🔧 API 호출: {metrics.get('api_calls', 0)}")
                print(f"      📄 답변 길이: {answer_length}자")

            except Exception as e:
                print(f"      ❌ 오류: {e}")
                question_results['modes'][mode] = {
                    "error": str(e),
                    "answer": None,
                    "response_time_ms": 0,
                    "total_tokens": 0,
                    "api_calls": 0
                }

        results.append(question_results)
        print(f"\n   {'='*70}")

    # 결과 저장
    if output_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"experiment_results_{timestamp}.json"

    output_path = os.path.join(os.path.dirname(__file__), '..', 'datasets', output_file)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_questions": len(questions),
            "modes": modes,
            "results": results
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*80}")
    print(f"✅ 실험 완료! 결과 저장: {output_path}")
    print(f"{'='*80}\n")

    # 간단한 요약 출력
    print_summary(results)

    return results


def print_summary(results):
    """실험 결과 요약 출력"""
    modes = ["vanilla", "current", "self_rag"]

    print(f"\n📊 실험 결과 요약")
    print(f"{'='*80}")

    # 모드별 평균 메트릭 계산
    for mode in modes:
        total_time = 0
        total_tokens = 0
        total_api_calls = 0
        success_count = 0
        error_count = 0

        for result in results:
            mode_result = result['modes'].get(mode, {})
            if 'error' not in mode_result:
                total_time += mode_result.get('response_time_ms', 0)
                total_tokens += mode_result.get('total_tokens', 0)
                total_api_calls += mode_result.get('api_calls', 0)
                success_count += 1
            else:
                error_count += 1

        if success_count > 0:
            avg_time = total_time / success_count
            avg_tokens = total_tokens / success_count
            avg_api_calls = total_api_calls / success_count

            print(f"\n🏷️  {mode.upper()}")
            print(f"   성공: {success_count}/{len(results)} | 실패: {error_count}")
            print(f"   평균 응답시간: {avg_time:.0f}ms ({avg_time/1000:.1f}초)")
            print(f"   평균 토큰: {avg_tokens:.0f}")
            print(f"   평균 API 호출: {avg_api_calls:.1f}")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="배치 모드 비교 실험")
    parser.add_argument("-o", "--output", help="출력 파일명 (기본: experiment_results_TIMESTAMP.json)")
    args = parser.parse_args()

    run_batch_experiment(output_file=args.output)
