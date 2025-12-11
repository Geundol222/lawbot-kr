"""
하이브리드 청킹 전략 예시
- 짧은 조문 (< 1500자): 조 단위 청킹
- 긴 조문 (≥ 1500자): 항 단위 청킹
"""

def smart_chunk_article(article_data: dict, threshold: int = 1500) -> list:
    """
    스마트 청킹: 조문 길이에 따라 조/항 단위 선택

    Args:
        article_data: 조문 데이터 (법령API 응답 형식)
        threshold: 조 단위 청킹 임계값 (기본 1500자)

    Returns:
        청크 리스트
    """
    법령명 = article_data['law_name']
    조문번호 = article_data['조문번호']
    조문제목 = article_data.get('조문제목', '')
    항_list = article_data['항']

    # 1. 전체 항 내용 합치기
    full_content_parts = []
    항_contents = []  # 항별 내용 따로 저장

    for 항 in 항_list:
        항내용 = 항.get('항내용', '')

        # 리스트 형식 처리
        if isinstance(항내용, list):
            항내용 = ' '.join([str(c) for c in 항내용 if c])

        # HTML 태그 제거
        항내용 = 항내용.replace('<br/>', ' ').replace('<br>', ' ')

        full_content_parts.append(항내용)
        항_contents.append(항내용)

    full_content = ' '.join(full_content_parts)

    # 2. 길이에 따라 청킹 전략 선택
    chunks = []

    if len(full_content) < threshold:
        # 짧은 조문: 조 전체를 하나의 청크로
        chunks.append({
            'law_name': 법령명,
            'article': f'제{조문번호}조',
            'title': 조문제목,
            'content': full_content,
            'chunk_type': 'full_article',  # 청킹 타입 표시
            'mst': article_data['mst']
        })

    else:
        # 긴 조문: 항 단위로 분리
        for idx, 항내용 in enumerate(항_contents, 1):
            if len(항내용) > 10:  # 내용이 있는 항만
                chunks.append({
                    'law_name': 법령명,
                    'article': f'제{조문번호}조',
                    'title': f"{조문제목} (제{idx}항)" if 조문제목 else f"제{idx}항",
                    'content': 항내용,
                    'chunk_type': 'by_hang',  # 항 단위 청킹 표시
                    'hang_number': idx,
                    'mst': article_data['mst']
                })

    return chunks


# ==========================================
# 예시 사용
# ==========================================

if __name__ == "__main__":
    # 예시 1: 짧은 조문 (민법 제750조)
    example_short = {
        'law_name': '민법',
        'mst': '000000',
        '조문번호': '750',
        '조문제목': '불법행위의 내용',
        '항': [
            {'항내용': '고의 또는 과실로 인한 위법행위로 타인에게 손해를 가한 자는 그 손해를 배상할 책임이 있다.'}
        ]
    }

    # 예시 2: 긴 조문 (근로기준법 제56조)
    example_long = {
        'law_name': '근로기준법',
        'mst': '000001',
        '조문번호': '56',
        '조문제목': '연장·야간 및 휴일 근로',
        '항': [
            {'항내용': '사용자는 연장근로(제53조·제59조 및 제69조 단서에 따라 연장된 시간의 근로)에 대하여는 통상임금의 100분의 50 이상을 가산하여 근로자에게 지급하여야 한다.' * 3},  # 길게 만들기
            {'항내용': '제1항에도 불구하고 사용자는 휴일근로에 대하여는 다음 각 호의 기준에 따른 금액 이상을 가산하여 근로자에게 지급하여야 한다.' * 3},
            {'항내용': '8시간 이내의 휴일근로: 통상임금의 100분의 50' * 2},
            {'항내용': '8시간을 초과한 휴일근로: 통상임금의 100분의 100' * 2},
        ]
    }

    print("=" * 80)
    print("하이브리드 청킹 예시")
    print("=" * 80)

    print("\n[예시 1] 짧은 조문 (민법 제750조)")
    print("-" * 80)
    chunks_short = smart_chunk_article(example_short)
    for chunk in chunks_short:
        print(f"법령: {chunk['law_name']} {chunk['article']}")
        print(f"타입: {chunk['chunk_type']}")
        print(f"길이: {len(chunk['content'])}자")
        print(f"내용: {chunk['content'][:100]}...")

    print("\n[예시 2] 긴 조문 (근로기준법 제56조)")
    print("-" * 80)
    chunks_long = smart_chunk_article(example_long, threshold=300)  # 낮춰서 테스트
    for chunk in chunks_long:
        print(f"법령: {chunk['law_name']} {chunk['article']}")
        print(f"타입: {chunk['chunk_type']}")
        if 'hang_number' in chunk:
            print(f"항: 제{chunk['hang_number']}항")
        print(f"길이: {len(chunk['content'])}자")
        print(f"내용: {chunk['content'][:100]}...")
        print()

    print("=" * 80)
    print("💡 하이브리드 청킹의 장점")
    print("=" * 80)
    print("✅ 짧은 조문: 전체 맥락 보존")
    print("✅ 긴 조문: 항별로 정확한 검색")
    print("✅ 청크 수: 적정 수준 유지")
    print("✅ 검색 품질: 향상")
