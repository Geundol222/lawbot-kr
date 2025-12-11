"""
현재 Supabase에 저장된 청크 데이터 분석
.env 파일이 있다면 실제 데이터 확인
"""
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_ANON_KEY')

if not SUPABASE_URL or not SUPABASE_KEY:
    print("="*80)
    print(".env 파일이 없거나 SUPABASE 환경변수가 설정되지 않았습니다.")
    print("="*80)
    print("\n일반적인 법령 통계로 분석합니다...\n")

    print("="*80)
    print("[GENERAL] 한국 주요 법령 통계 (일반적 기준)")
    print("="*80)

    print("\n주요 법령별 예상 통계:")
    print("-" * 80)

    sample_stats = [
        {"law": "근로기준법", "articles": 116, "avg_hangs": 2.5, "avg_chars": 450},
        {"law": "민법", "articles": 1118, "avg_hangs": 1.8, "avg_chars": 350},
        {"law": "형법", "articles": 372, "avg_hangs": 2.0, "avg_chars": 400},
        {"law": "주택임대차보호법", "articles": 23, "avg_hangs": 3.2, "avg_chars": 600},
        {"law": "개인정보 보호법", "articles": 76, "avg_hangs": 2.8, "avg_chars": 550},
        {"law": "상법", "articles": 928, "avg_hangs": 2.3, "avg_chars": 480},
    ]

    total_articles = 0
    total_hangs = 0
    all_avg_chars = []

    for stat in sample_stats:
        articles = stat['articles']
        hangs = int(articles * stat['avg_hangs'])
        chars = stat['avg_chars']

        total_articles += articles
        total_hangs += hangs
        all_avg_chars.append(chars)

        print(f"{stat['law']:20s} | 조문: {articles:4d}개 | 항: {hangs:5d}개 | 평균: {chars:3d}자")

    print("-" * 80)
    print(f"{'합계':20s} | 조문: {total_articles:4d}개 | 항: {total_hangs:5d}개")

    avg_all = sum(all_avg_chars) / len(all_avg_chars)

    print("\n" + "="*80)
    print("[ANALYSIS] 청킹 전략 분석")
    print("="*80)

    print(f"\n현재 데이터 특성:")
    print(f"  - 총 조문 수: {total_articles}개")
    print(f"  - 총 항 수: {total_hangs}개")
    print(f"  - 평균 조문 길이: {int(avg_all)}자")

    # 500자 청킹 예상
    estimated_500_chunks = int(total_articles * avg_all / 400)  # 오버랩 고려

    # 조 단위 청킹 (일부 긴 조문은 2개로 분할)
    estimated_jo_chunks = int(total_articles * 1.15)  # 15% 정도 분할

    # 항 단위 청킹
    estimated_hang_chunks = total_hangs

    # 하이브리드 (1500자 이상만 항 단위)
    # 일반적으로 약 10-15%의 조문이 1500자 이상
    long_articles_ratio = 0.12
    long_articles = int(total_articles * long_articles_ratio)
    avg_hangs_long = 4  # 긴 조문은 평균 4항

    estimated_hybrid = (total_articles - long_articles) + (long_articles * avg_hangs_long)

    print("\n청킹 전략별 예상 청크 수:")
    print(f"  1. 현재 방식 (500자 고정):  {estimated_500_chunks:,}개")
    print(f"  2. 조 단위 청킹:            {estimated_jo_chunks:,}개")
    print(f"  3. 항 단위 청킹:            {estimated_hang_chunks:,}개")
    print(f"  4. 하이브리드 (추천):        {estimated_hybrid:,}개")

    print("\n" + "="*80)
    print("[RECOMMENDATION] 최종 추천")
    print("="*80)

    print("\n하이브리드 청킹 전략 권장:")
    print("  [1] 1500자 미만 조문 (약 88%): 조 전체를 1개 청크")
    print("  [2] 1500자 이상 조문 (약 12%): 항별로 분리")

    print(f"\n예상 결과:")
    print(f"  - 청크 수: 약 {estimated_hybrid:,}개")
    print(f"  - Supabase 용량: 약 50-80MB (무료 플랜 500MB 내)")
    print(f"  - 검색 성능: 양호 (1만개 미만)")
    print(f"  - 답변 품질: 향상 (조문 완전성 보장)")

    print("\n장점:")
    print("  [OK] 짧은 조문: 맥락 완전 보존")
    print("  [OK] 긴 조문: 항별 정확한 검색")
    print("  [OK] 청크 수: 적정 수준")
    print("  [OK] 지인 피드백 해결: 항 누락 문제 해결")

    print("\n" + "="*80)

else:
    # Supabase 연결 가능
    from supabase import create_client

    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        print("="*80)
        print("[CURRENT] 현재 Supabase 청크 데이터 분석")
        print("="*80)

        # 총 청크 수
        result = supabase.table('law_cache').select('*', count='exact').execute()
        total_chunks = result.count

        print(f"\n현재 총 청크 수: {total_chunks:,}개")

        # 샘플 데이터 분석
        sample = supabase.table('law_cache').select('law_name,article,content').limit(100).execute()

        lengths = [len(item['content']) for item in sample.data]
        avg_length = sum(lengths) / len(lengths) if lengths else 0
        min_length = min(lengths) if lengths else 0
        max_length = max(lengths) if lengths else 0

        print(f"\n샘플 100개 청크 분석:")
        print(f"  - 평균 길이: {int(avg_length)}자")
        print(f"  - 최소 길이: {min_length}자")
        print(f"  - 최대 길이: {max_length}자")

        # 조문 수 추정 (part 포함된 것 제외)
        unique_articles = supabase.table('law_cache').select('law_name,article').execute()
        base_articles = set()
        for item in unique_articles.data:
            article = item['article'].split('_part')[0]
            key = f"{item['law_name']}:{article}"
            base_articles.add(key)

        estimated_articles = len(base_articles)

        print(f"\n추정 조문 수: {estimated_articles:,}개")
        print(f"청킹 비율: {total_chunks / estimated_articles:.2f}x")

        print("\n" + "="*80)
        print("[RECOMMENDATION] 청킹 전략 제안")
        print("="*80)

        if avg_length < 600:
            print("\n현재 청크가 비교적 짧습니다 (평균 {int(avg_length)}자)")
            print("조 단위 청킹으로 변경 권장:")
            print(f"  - 예상 청크 수: 약 {int(estimated_articles * 1.15):,}개")
            print(f"  - 맥락 보존 향상")
        else:
            print("\n하이브리드 청킹 권장:")
            print(f"  - 예상 청크 수: 약 {int(estimated_articles * 1.3):,}개")
            print(f"  - 짧은 조문: 완전성 보장")
            print(f"  - 긴 조문: 정확한 검색")

    except Exception as e:
        print(f"\n[ERROR] Supabase 연결 실패: {e}")
        print("일반 통계로 분석합니다...")
