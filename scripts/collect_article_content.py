"""
Ground Truth에 실제 법령 조문 내용 자동 추가

목적:
- Ground Truth의 articles에 명시된 조문의 실제 내용을 법령 API로 조회
- article_content 필드에 저장 (Faithfulness 평가 시 사용)

사용법:
    python scripts/collect_article_content.py
"""

import json
import sys
from pathlib import Path
from tqdm import tqdm

# Windows console encoding fix
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# backend 경로 추가
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from src.law_api import search_and_get_law, extract_article_content


def parse_article_reference(article_ref: str) -> tuple:
    """
    "민법 750" → ("민법", "750")
    "근로기준법 56" → ("근로기준법", "56")

    Returns:
        (law_name, article_number)
    """
    parts = article_ref.strip().split()
    if len(parts) >= 2:
        law_name = " ".join(parts[:-1])  # "근로기준법"
        article = parts[-1]  # "56"
        return law_name, article
    else:
        return article_ref, ""


def collect_article_content(ground_truth_path: str):
    """
    Ground Truth의 articles에 대해 실제 법령 조문 내용 수집

    Args:
        ground_truth_path: Ground Truth JSON 경로 (업데이트됨)
    """
    print(f"\n{'='*60}")
    print(f"📜 법령 조문 내용 수집 시작")
    print(f"{'='*60}\n")

    # Ground Truth 로드
    with open(ground_truth_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    total_articles = 0
    collected_count = 0
    failed_count = 0

    for qid, gt in tqdm(ground_truth.items(), desc="조문 수집 중"):
        articles = gt.get("articles", [])
        if not articles:
            continue

        # article_content 초기화
        if "article_content" not in gt:
            gt["article_content"] = {}

        for article_ref in articles:
            total_articles += 1

            # 이미 수집된 조문은 건너뛰기 (None이 아닌 경우에만)
            if article_ref in gt["article_content"] and gt["article_content"][article_ref] is not None:
                print(f"⏭️  {qid} - {article_ref}: 이미 수집됨")
                collected_count += 1
                continue

            # 법령명과 조문 번호 파싱
            law_name, article_num = parse_article_reference(article_ref)

            if not article_num:
                print(f"⚠️  {qid} - {article_ref}: 파싱 실패")
                failed_count += 1
                continue

            # 법령 API 조회
            try:
                # search_and_get_law()로 법령 검색 + 조문 조회
                result = search_and_get_law(law_name, article_num)

                if result and not result.get("error"):
                    # extract_article_content()로 조문 내용 추출
                    content = extract_article_content(result)

                    # 디버깅: content 값 확인
                    print(f"   [DEBUG] content type: {type(content)}, length: {len(content) if content else 0}")
                    print(f"   [DEBUG] content value: {repr(content[:100]) if content else 'None'}")

                    # 내용 검증 (빈 문자열, 오류 메시지 제외)
                    if content and len(content.strip()) > 0 and not content.startswith("오류:") and not content.startswith("조문 정보를"):
                        gt["article_content"][article_ref] = content
                        collected_count += 1
                        print(f"✅ {qid} - {article_ref}: 수집 완료")
                        print(f"   내용: {content[:100]}...")
                    else:
                        reason = "빈 문자열" if not content or len(content.strip()) == 0 else content[:50]
                        print(f"❌ {qid} - {article_ref}: 조문 내용 추출 실패 ({reason})")
                        gt["article_content"][article_ref] = None
                        failed_count += 1
                else:
                    error_msg = result.get("error", "Unknown") if result else "No result"
                    print(f"❌ {qid} - {article_ref}: API 오류 - {error_msg}")
                    gt["article_content"][article_ref] = None
                    failed_count += 1

            except Exception as e:
                print(f"❌ {qid} - {article_ref}: 예외 발생 - {e}")
                import traceback
                traceback.print_exc()
                gt["article_content"][article_ref] = None
                failed_count += 1

    # Ground Truth 저장
    print(f"\n💾 Ground Truth 저장 중: {ground_truth_path}")
    with open(ground_truth_path, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"✅ 법령 조문 내용 수집 완료!")
    print(f"{'='*60}")
    print(f"총 조문: {total_articles}개")
    print(f"수집 성공: {collected_count}개")
    print(f"수집 실패: {failed_count}개\n")


def verify_article_content(ground_truth_path: str):
    """
    수집된 조문 내용 검증

    Args:
        ground_truth_path: Ground Truth JSON 경로
    """
    print(f"\n{'='*60}")
    print(f"🔍 조문 내용 검증")
    print(f"{'='*60}\n")

    with open(ground_truth_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    total_questions = len(ground_truth)
    total_articles = 0
    with_content = 0
    without_content = 0

    for qid, gt in ground_truth.items():
        articles = gt.get("articles", [])
        article_content = gt.get("article_content", {})

        for article_ref in articles:
            total_articles += 1

            if article_ref in article_content:
                if article_content[article_ref]:
                    with_content += 1
                else:
                    without_content += 1
                    print(f"⚠️  {qid} - {article_ref}: 내용 없음 (None)")
            else:
                without_content += 1
                print(f"❌ {qid} - {article_ref}: article_content에 없음")

    print(f"\n총 질문: {total_questions}개")
    print(f"총 조문: {total_articles}개")
    print(f"내용 있음: {with_content}개")
    print(f"내용 없음: {without_content}개\n")

    if without_content > 0:
        print(f"⚠️  경고: {without_content}개 조문의 내용이 없습니다.")
        print("   법령명이나 조문 번호를 확인하세요.\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="법령 조문 내용 수집")
    parser.add_argument(
        "--ground_truth",
        type=str,
        default="datasets/ground_truth.json",
        help="Ground Truth JSON 경로"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="조문 내용 검증만 수행"
    )

    args = parser.parse_args()

    if args.verify:
        # 검증만 수행
        verify_article_content(args.ground_truth)
    else:
        # 수집 실행
        collect_article_content(args.ground_truth)

        # 수집 후 자동 검증
        verify_article_content(args.ground_truth)
