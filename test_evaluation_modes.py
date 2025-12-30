"""
평가 모드 테스트 스크립트

3개 모드 (vanilla, current, self_rag)가 정상 작동하는지 확인
"""
import sys
from pathlib import Path

# backend 경로 추가
backend_path = Path(__file__).parent / 'backend'
sys.path.insert(0, str(backend_path))

from src.agentic_rag import AgenticRAG

def test_evaluation_modes():
    """3개 모드 테스트"""

    test_question = "근로기준법 제56조에 대해 알려줘"

    modes = ["vanilla", "current", "self_rag"]

    print("=" * 60)
    print("평가 모드 테스트")
    print("=" * 60)

    for mode in modes:
        print(f"\n{'='*60}")
        print(f"테스트: {mode} 모드")
        print(f"{'='*60}")

        try:
            # AgenticRAG 초기화
            agent = AgenticRAG(mode=mode)

            # run_with_metrics 실행
            result = agent.run_with_metrics(test_question)

            # 결과 출력
            print(f"\n[답변]")
            print(result["answer"][:200] + "..." if len(result["answer"]) > 200 else result["answer"])

            print(f"\n[메트릭]")
            print(f"  - 응답 시간: {result['metrics']['response_time_ms']}ms")
            print(f"  - 토큰 수: {result['metrics']['total_tokens']}")
            print(f"  - API 호출: {result['metrics']['api_calls']}")
            print(f"  - 검색 반복: {result['metrics']['search_iterations']}")
            print(f"  - 모드: {result['metrics']['mode']}")

            print(f"\n[검색된 문서]")
            print(f"  - 총 {len(result['retrieved_docs'])}개")
            for idx, doc in enumerate(result['retrieved_docs'][:3], 1):
                print(f"    {idx}. {doc.get('law_name', 'N/A')} {doc.get('article', 'N/A')} (유사도: {doc.get('similarity', 0):.2f})")

            print(f"\n✅ {mode} 모드 테스트 성공!")

        except Exception as e:
            print(f"\n❌ {mode} 모드 테스트 실패: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'='*60}")
    print("테스트 완료!")
    print(f"{'='*60}")

if __name__ == "__main__":
    test_evaluation_modes()
