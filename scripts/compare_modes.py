"""
모드별 답변 비교 스크립트

3개 모드(vanilla, current, self_rag)의 답변을 나란히 비교
"""
import sys
from pathlib import Path

# backend 경로 추가
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from src.agentic_rag import AgenticRAG


def compare_modes(question: str):
    """3개 모드의 답변을 비교"""

    modes = ["vanilla", "current", "self_rag"]
    results = {}

    print("=" * 100)
    print(f"질문: {question}")
    print("=" * 100)

    for mode in modes:
        print(f"\n{'='*100}")
        print(f"🔍 {mode.upper()} 모드 실행 중...")
        print(f"{'='*100}")

        try:
            agent = AgenticRAG(mode=mode)
            result = agent.run_with_metrics(question)
            results[mode] = result

            print(f"\n✅ {mode} 완료!")
            print(f"   응답 시간: {result['metrics']['response_time_ms']}ms")
            print(f"   토큰 수: {result['metrics']['total_tokens']}")
            print(f"   API 호출: {result['metrics']['api_calls']}")

        except Exception as e:
            print(f"\n❌ {mode} 실패: {e}")
            import traceback
            traceback.print_exc()

    # 비교 결과 출력
    print("\n" + "=" * 100)
    print("📊 답변 비교")
    print("=" * 100)

    for mode in modes:
        if mode not in results:
            continue

        result = results[mode]

        print(f"\n{'='*100}")
        print(f"🏷️  {mode.upper()} 모드")
        print(f"{'='*100}")
        print(f"\n⏱️  응답 시간: {result['metrics']['response_time_ms']}ms")
        print(f"💰 토큰 수: {result['metrics']['total_tokens']}")
        print(f"🔧 API 호출: {result['metrics']['api_calls']}")
        print(f"📚 검색 문서: {len(result['retrieved_docs'])}개")

        # 검색된 문서 목록
        print(f"\n📋 검색된 조문:")
        for idx, doc in enumerate(result['retrieved_docs'][:5], 1):
            print(f"   {idx}. {doc.get('law_name', 'N/A')} {doc.get('article', 'N/A')} (유사도: {doc.get('similarity', 0):.2f})")

        # 답변 (처음 500자만)
        answer = result['answer']
        print(f"\n💬 답변 (처음 500자):")
        print("-" * 100)
        print(answer[:500] + ("..." if len(answer) > 500 else ""))
        print("-" * 100)

    # 메트릭 비교 테이블
    print(f"\n{'='*100}")
    print("📊 메트릭 비교 테이블")
    print(f"{'='*100}")
    print(f"{'모드':<12} | {'응답시간(ms)':<15} | {'토큰':<10} | {'API호출':<10} | {'검색문서':<10}")
    print("-" * 100)

    for mode in modes:
        if mode not in results:
            continue
        result = results[mode]
        metrics = result['metrics']
        print(f"{mode:<12} | {metrics['response_time_ms']:<15} | {metrics['total_tokens']:<10} | {metrics['api_calls']:<10} | {len(result['retrieved_docs']):<10}")

    print("=" * 100)

    return results


if __name__ == "__main__":
    # 테스트 질문들
    test_questions = [
        "근로기준법 제56조에 대해 알려줘",
        "5인 미만 사업장에서 해고 예고수당은 어떻게 되나요?",
        "교통사고로 다쳤을 때 손해배상은 어떻게 받나요?",
    ]

    # 사용자가 질문을 입력하면 그걸 사용, 아니면 첫 번째 테스트 질문 사용
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        print("\n사용법: python scripts/compare_modes.py \"질문\"")
        print(f"\n기본 질문 사용: {test_questions[0]}\n")
        question = test_questions[0]

    compare_modes(question)
