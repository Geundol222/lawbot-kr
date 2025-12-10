"""
법령 조문 길이 분석 스크립트
- 조 단위 vs 항 단위 청킹 결정을 위한 통계 분석
"""
import requests
import json
import time
from typing import Dict, List

# 샘플 법령 (주요 법령 중 일부)
SAMPLE_LAWS = [
    "근로기준법",
    "민법",
    "형법",
    "주택임대차보호법",
    "개인정보 보호법"
]

LAW_API_SEARCH = "https://www.law.go.kr/DRF/lawSearch.do"
LAW_API_SERVICE = "https://www.law.go.kr/DRF/lawService.do"
LAW_API_OC = "your_key_here"  # 임시로 넣어두고 환경변수에서 가져오도록


def search_law_mst(law_name: str) -> str:
    """법령 MST 검색"""
    params = {
        'OC': LAW_API_OC,
        'target': 'law',
        'type': 'JSON',
        'query': law_name,
        'display': 10
    }

    try:
        response = requests.get(LAW_API_SEARCH, params=params, timeout=30)
        data = response.json()

        law_list = data.get('LawSearch', {}).get('law', [])
        if isinstance(law_list, dict):
            law_list = [law_list]

        for law in law_list:
            if law.get('법령명한글') == law_name:
                return law.get('법령일련번호')
        return None
    except Exception as e:
        print(f"에러: {e}")
        return None


def analyze_law_structure(mst: str, law_name: str) -> Dict:
    """법령 구조 분석"""
    params = {
        'OC': LAW_API_OC,
        'target': 'law',
        'type': 'JSON',
        'MST': mst
    }

    try:
        response = requests.get(LAW_API_SERVICE, params=params, timeout=30)
        data = response.json()

        조문_list = data.get('법령', {}).get('조문', {}).get('조문단위', [])
        if isinstance(조문_list, dict):
            조문_list = [조문_list]

        stats = {
            'law_name': law_name,
            'total_articles': len(조문_list),
            'article_lengths': [],
            'hang_counts': [],
            'long_articles': [],  # 1500자 이상
            'total_hangs': 0
        }

        for 조문 in 조문_list:
            조문번호 = 조문.get('조문번호', '')
            항_list = 조문.get('항', [])

            if isinstance(항_list, dict):
                항_list = [항_list]

            # 조 전체 내용 합치기
            full_content = []
            for 항 in 항_list:
                항내용 = 항.get('항내용', '')
                if isinstance(항내용, list):
                    항내용 = ' '.join([str(c) for c in 항내용 if c])
                full_content.append(str(항내용))

            조_전체 = ' '.join(full_content)
            조_길이 = len(조_전체)

            stats['article_lengths'].append(조_길이)
            stats['hang_counts'].append(len(항_list))
            stats['total_hangs'] += len(항_list)

            if 조_길이 > 1500:
                stats['long_articles'].append({
                    'article': f'제{조문번호}조',
                    'length': 조_길이,
                    'hang_count': len(항_list)
                })

        return stats

    except Exception as e:
        print(f"에러: {e}")
        return None


def main():
    """메인 분석"""
    print("="*80)
    print("법령 조문 길이 분석")
    print("="*80)

    all_stats = []

    for law_name in SAMPLE_LAWS:
        print(f"\n[INFO] {law_name} 분석 중...")

        mst = search_law_mst(law_name)
        if not mst:
            print(f"  [FAIL] MST를 찾을 수 없습니다")
            continue

        stats = analyze_law_structure(mst, law_name)
        if not stats:
            print(f"  [FAIL] 분석 실패")
            continue

        all_stats.append(stats)

        print(f"  [OK] 총 조문 수: {stats['total_articles']}개")
        print(f"  [OK] 총 항 수: {stats['total_hangs']}개")

        if stats['article_lengths']:
            avg_length = sum(stats['article_lengths']) / len(stats['article_lengths'])
            max_length = max(stats['article_lengths'])
            print(f"  [STAT] 평균 조문 길이: {int(avg_length)}자")
            print(f"  [STAT] 최대 조문 길이: {max_length}자")

        if stats['long_articles']:
            print(f"  [WARN] 1500자 이상 조문: {len(stats['long_articles'])}개")
            for item in stats['long_articles'][:3]:
                print(f"     - {item['article']}: {item['length']}자 ({item['hang_count']}항)")

        time.sleep(2)

    # 전체 통계
    print("\n" + "="*80)
    print("[SUMMARY] 전체 통계")
    print("="*80)

    total_articles = sum(s['total_articles'] for s in all_stats)
    total_hangs = sum(s['total_hangs'] for s in all_stats)
    all_lengths = [l for s in all_stats for l in s['article_lengths']]

    print(f"\n총 조문 수: {total_articles}개")
    print(f"총 항 수: {total_hangs}개")

    if all_lengths:
        print(f"\n조문 길이 통계:")
        print(f"  - 평균: {int(sum(all_lengths)/len(all_lengths))}자")
        print(f"  - 최소: {min(all_lengths)}자")
        print(f"  - 최대: {max(all_lengths)}자")

        # 길이별 분포
        short = len([l for l in all_lengths if l < 500])
        medium = len([l for l in all_lengths if 500 <= l < 1500])
        long = len([l for l in all_lengths if l >= 1500])

        print(f"\n길이 분포:")
        print(f"  - 500자 미만: {short}개 ({short/len(all_lengths)*100:.1f}%)")
        print(f"  - 500-1500자: {medium}개 ({medium/len(all_lengths)*100:.1f}%)")
        print(f"  - 1500자 이상: {long}개 ({long/len(all_lengths)*100:.1f}%)")

    print("\n" + "="*80)
    print("[RECOMMENDATION] 청킹 전략 제안")
    print("="*80)

    if all_lengths:
        avg = sum(all_lengths) / len(all_lengths)
        long_ratio = len([l for l in all_lengths if l >= 1500]) / len(all_lengths)

        print(f"\n현재 데이터 특성:")
        print(f"  - 평균 조문 길이: {int(avg)}자")
        print(f"  - 긴 조문 비율: {long_ratio*100:.1f}%")
        print(f"  - 조 단위 청킹 시: 약 {total_articles}개 청크")
        print(f"  - 항 단위 청킹 시: 약 {total_hangs}개 청크")

        print(f"\n추천 전략:")
        if avg < 1000:
            print("  [BEST] 조 단위 청킹 권장")
            print("     - 대부분 조문이 1000자 미만")
            print("     - 맥락 보존에 유리")
        elif long_ratio > 0.3:
            print("  [BEST] 하이브리드 청킹 권장")
            print("     - 1500자 미만: 조 단위")
            print("     - 1500자 이상: 항 단위")
        else:
            print("  [WARN] 데이터 특성 재검토 필요")


if __name__ == "__main__":
    # 환경변수 로드
    try:
        from dotenv import load_dotenv
        import os
        # backend 폴더의 .env 파일 로드
        from pathlib import Path
        env_path = Path(__file__).parent / 'backend' / '.env'
        load_dotenv(env_path)
        LAW_API_OC = os.getenv('LAW_API_OC')

        if not LAW_API_OC:
            print("[ERROR] LAW_API_OC 환경변수가 설정되지 않았습니다.")
            print("   .env 파일을 확인하거나 직접 LAW_API_OC 변수를 설정하세요.")
            exit(1)
    except ImportError:
        print("[ERROR] python-dotenv가 설치되지 않았습니다.")
        exit(1)

    main()
