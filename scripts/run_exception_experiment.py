"""
예외 케이스 집중 실험 (q011~q015)
Self-RAG가 법률 도메인에서 오히려 혼란을 야기하는지 검증
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import json
import time
from datetime import datetime
from src.agentic_rag import AgenticRAG


def run_exception_experiment():
    """예외 케이스 집중 실험"""

    # 예외 케이스만 필터링 (q011~q015)
    questions_file = os.path.join(os.path.dirname(__file__), '..', 'datasets', 'eval_questions.json')
    with open(questions_file, 'r', encoding='utf-8') as f:
        all_questions = json.load(f)

    questions = [q for q in all_questions if q['id'] in ['q011', 'q012', 'q013', 'q014', 'q015']]

    modes = ["vanilla", "current", "self_rag"]
    results = []

    print(f"\n{'='*80}")
    print(f"🧪 예외 케이스 집중 실험")
    print(f"   질문: {len(questions)}개 (exception_scope 카테고리)")
    print(f"   모드: {len(modes)}개 (vanilla, current, self_rag)")
    print(f"   총 실행: {len(questions) * len(modes)}회")
    print(f"{'='*80}\n")

    for idx, q_item in enumerate(questions, 1):
        question_id = q_item['id']
        question = q_item['question']
        note = q_item.get('note', '')

        print(f"\n{'='*80}")
        print(f"[{idx}/{len(questions)}] {question_id}: {question}")
        print(f"💡 주석: {note}")
        print(f"{'='*80}\n")

        question_results = {
            "question_id": question_id,
            "question": question,
            "note": note,
            "modes": {}
        }

        for mode in modes:
            print(f"\n🏷️  모드: {mode.upper()}")
            print(f"{'─'*70}")
            try:
                start = time.time()
                agent = AgenticRAG(mode=mode)
                result = agent.run_with_metrics(question)
                elapsed = time.time() - start

                metrics = result.get('metrics', {})
                answer = result.get('answer', '')

                # 답변에서 핵심 결론 추출 (첫 200자)
                answer_preview = answer[:200] + "..." if len(answer) > 200 else answer

                question_results['modes'][mode] = {
                    "answer": answer,
                    "answer_preview": answer_preview,
                    "answer_length": len(answer),
                    "response_time_ms": metrics.get('response_time_ms', 0),
                    "total_tokens": metrics.get('total_tokens', 0),
                    "api_calls": metrics.get('api_calls', 0),
                    "search_iterations": metrics.get('search_iterations', 0),
                    "retrieved_docs_count": len(result.get('retrieved_docs', []))
                }

                print(f"⏱️  응답시간: {metrics.get('response_time_ms', 0)}ms ({elapsed:.1f}초)")
                print(f"💰 토큰: {metrics.get('total_tokens', 0)} | API 호출: {metrics.get('api_calls', 0)}")
                print(f"📚 검색 문서: {len(result.get('retrieved_docs', []))}개")
                print(f"\n📝 답변 미리보기:")
                print(f"   {answer_preview}")

            except Exception as e:
                import traceback
                print(f"❌ 오류: {e}")
                traceback.print_exc()
                question_results['modes'][mode] = {
                    "error": str(e),
                    "answer": None,
                    "response_time_ms": 0,
                    "total_tokens": 0,
                    "api_calls": 0
                }

            print(f"{'─'*70}")

        results.append(question_results)

    # 결과 저장
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"exception_experiment_{timestamp}.json"
    output_path = os.path.join(os.path.dirname(__file__), '..', 'datasets', output_file)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "experiment_type": "exception_scope_focused",
            "total_questions": len(questions),
            "modes": modes,
            "results": results
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*80}")
    print(f"✅ 실험 완료! 결과 저장: {output_file}")
    print(f"{'='*80}\n")

    # 요약 출력
    print_summary(results)

    return results, output_path


def print_summary(results):
    """실험 결과 요약"""
    modes = ["vanilla", "current", "self_rag"]

    print(f"\n{'='*80}")
    print(f"📊 실험 결과 요약")
    print(f"{'='*80}\n")

    # 모드별 평균 메트릭
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

            print(f"🏷️  {mode.upper()}")
            print(f"   성공률: {success_count}/{len(results)}")
            print(f"   평균 응답시간: {avg_time:.0f}ms ({avg_time/1000:.1f}초)")
            print(f"   평균 토큰: {avg_tokens:.0f}")
            print(f"   평균 API 호출: {avg_api_calls:.1f}")
            print()

    print(f"{'='*80}\n")


if __name__ == "__main__":
    run_exception_experiment()
