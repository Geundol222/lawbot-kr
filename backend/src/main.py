"""실험용 엔트리포인트.

- 단일 질문을 인자로 받거나
- 인자가 없으면 REPL 형태로 여러 질문을 연속 실행

AgenticRAG의 실제 호출 경로를 빠르게 확인하기 위해 작성했습니다.
"""

import argparse
import sys

from src.agentic_rag import AgenticRAG


def run_once(agent: AgenticRAG, question: str) -> None:
    """주어진 질문으로 AgenticRAG를 실행하고 결과를 출력."""
    try:
        answer = agent.run(question)
        print("\n📝 최종 답변\n" + "-" * 40)
        print(answer)
        print("-" * 40 + "\n")
    except Exception as exc:
        print(f"⚠️ 실행 실패: {exc}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description="AgenticRAG 실험용 실행기")
    parser.add_argument(
        "question",
        nargs="?",
        help="단일 질문. 없으면 대화형 입력 모드로 실행됩니다.",
    )
    args = parser.parse_args()

    agent = AgenticRAG()

    if args.question:
        run_once(agent, args.question)
        return

    # 대화형 모드
    print("AgenticRAG 대화형 모드입니다. 종료하려면 빈 줄을 입력하세요.")
    while True:
        try:
            user_input = input("\n질문> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n종료합니다.")
            break

        if not user_input:
            print("종료합니다.")
            break

        run_once(agent, user_input)


if __name__ == "__main__":
    main()
