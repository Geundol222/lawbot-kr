# TODO

## 2025.12.06
1. WandB 로깅 전략 개선 필요
- 현재: 버전마다 run 생성
- 개선안 1: 기기마다 고유 uuid 생성 → Supabase에 uuid별 저장 → WandB에 uuid별 run
- 개선안 2: 버전별 run + 기기별 처리 현황 분리 저장

2. 벡터서치 정확도 문제
- 고용노동부 재직 인원 피드백: 애매하거나 틀린 답변 생성
- 원인 추정: 조문 일부만 반환
- 해결 방안: 조문 기반 검색 후 해당 조문의 모든 content 가져오기
- 청킹 전략: 조문별 청킹 적용

3. 응답 속도 개선
- 현재: 평균 6-15초 (실시간 generating 부적합)
- 해결책: 스트리밍 방식 적용 (글자 하나씩 타이핑)
- 추가: 벡터 서치 semantic 최적화

4. Agentic 개선
- 현재: LangGraph 사용하지만 기본 LangChain과 동일
- 추가 필요: LLM 자체평가, 재시도 백오프 등

5. 테스트/운영 자동화
- 자동화된 테스트, 스키마 검증, 에이전트 툴 통합 테스트
- CI 포함 품질 개선 테스트 케이스

6. 모듈 최적화
- 문제: Streamlit 다중 프로세스에서 모델 중복 로드 → 메모리 낭비, 스타트업 지연
- 해결책: 지연 로딩, 싱글톤 캐싱


## 2025.12.10
1. 조 단위 청킹 완료
- 문제: 예외조항/적용범위 고려하지 않아 답변 신뢰도 낮음
- 해결 방안 검토: LLM 기반 관계 분석, 프롬프트 강화, GraphDB 전환, 하이브리드 검색
- 결론: 현재는 프롬프트 개선으로 대응, 고도화는 추후

2. LLM 스트리밍 출력 구현
- backend: `run_stream()` 메서드 추가
- API: `/chat/stream` 엔드포인트 (SSE)
- Frontend: Next.js + React 스트리밍 UI
- 체감 속도: 10초 → 0.5초 (20배 개선)

3. 하이브리드 LLM 전략
- Tool calling: Gemini 2.0 Flash Thinking (정확한 법령명 추론)
- 답변 생성: Gemini 2.5 Flash (빠른 생성)
- 효과: 법령명 매핑 정확도 70% → 95%
- 비용/속도: Pro 대비 10배 빠르고 저렴

4. 브랜치 전략 수정
- main 브랜치 기본 사용 (Vercel, HuggingFace 연동)
- develop 브랜치 백업용


## 2025.12.11
1. 코드 모듈화
- `agentic_rag.py` 509줄 → 238줄로 축소
- 분리: `agent_state.py`, `agent_nodes.py`, `agent_streaming.py`
- 객체지향 설계 적용, 유지보수성 향상

2. LLM 설정 간소화
- 3가지 용도 → 2가지 모델 (flash, flash-lite)
- `AgenticRAG` 클래스: 중복 LLM 인스턴스 제거 → 단일 인스턴스
- 싱글톤 패턴 유지로 메모리 효율화

3. 스트리밍 기능 완전 구현
- 기존 문제: 그래프 완료 후 가짜 스트리밍 (5자 청크 즉시 전송)
- 개선: 1자씩 30ms 간격 전송 → 자연스러운 타이핑 효과
- Gemini 응답 형식 처리 개선 (문자열 + 리스트 형식 모두 지원)
- 로컬 Streamlit 테스트 완료 (ChatGPT 수준)

4. 성능 최적화
- Tool calling LLM: gemini-2.5-pro → gemini-2.5-flash
- 그래프 실행 12초 → 3-6초 예상
- 벡터 검색 병목 확인: 2-3초 (Supabase RPC)
- 단계별 타이밍 로그 추가

5. CI/CD 파이프라인 구축
- pytest 기반 테스트 프레임워크 (Unit, Integration 테스트)
- GitHub Actions 자동화 (CI: 자동 테스트, CD: HuggingFace + Vercel 배포)
- 코드 품질 검사: flake8, black, isort, mypy
- Python 3.12 고정 (networkx 3.6 호환성)

6. WandB 로깅 전략 개선
- 기존: 모든 요청이 하나의 run → 분석 어려움
- 개선: 세션별 Run 전략
  - Group: 날짜별 (`daily_20251211`)
  - Run: 세션별 (`session-abc123_143022`)
  - Step: 대화 턴별 (1, 2, 3...)
- 예상 Run 수: 일 10~100개
- 장점: 사용자별 대화 흐름 추적, 날짜별 트렌드 분석

7. 프론트엔드 UX 개선
- 스크롤 자동 내려가는 문제 해결
- 사용자가 위로 스크롤하면 자동 스크롤 중지
- "아래로 이동" 버튼 추가 (bounce 애니메이션)
- 스트리밍 중 스크롤 동작 최적화

8. 남은 작업
- HuggingFace + Vercel 배포 후 실제 스트리밍 테스트
- 벡터 검색 속도 최적화 (인덱싱, 캐싱)
- 프론트엔드 로딩 UI 개선
- Supabase 저장 비동기 처리
- 세션 타임아웃 구현 (30분 무활동 시 WandB run 종료)
- 프론트엔드 `beforeunload` 이벤트로 세션 종료 처리


## 2025.12.12
1. Tool calling 2단계 구조
- 1차: 프론트엔드에 "법령을 검색 중입니다..." 출력
- 2차: 예외 조항/적용범위 탐색 필요 여부 판단 (`check_exceptions_needed` 함수, gemini-2.5-flash-lite)

2. 예외 조항/적용 범위 탐색 필요 시
- 프론트엔드에 "예외 조항이 있는 것 같습니다 예외 조항을 검색중입니다..." 출력
- 기본 법령 + 예외 조항 합쳐서 RAG
- 라이브 스트리밍 효과

3. 예외 조항 불필요 시
- 프론트엔드에 바로 법령 출력
- 라이브 스트리밍 효과

4. API 호출 최적화
- 문제: function calling 시 모든 관련 조문 가져와서 문맥 과다
- 해결: 관련 조문 검색 후 semantic search로 키워드 맞는 조문만 선택
- 효과: 처리 시간 효과적으로 단축, 정확성과 문맥 이해도 상승

5. VectorDB 조문 누락 문제
- `generate_embeddings.py` 코드 확인 및 수정 (너무 짧거나 API 호출 오류)
- 시행령/시행규칙 등 예외조항 포함하여 검색 정확성 향상
- 정보 양 대폭 상승


## 2025.12.13
1. VectorDB 재구축 완료
- 근로기준법 제26조(해고의 예고) 누락 문제 해결
- API 응답 구조 버그 수정 (법령명한글 키, 항 구조, 전문 필터링)
- 시행령/시행규칙 85개 법령 추가 (기존 28개 → 85개)
- 최종 결과: 11,110개 조문 수집 (81/85개 법령 성공)
- 실패 4개: 상법, 상법 시행령, 소비자기본법 시행규칙, 개인정보 보호법 시행규칙 (API MST 없음)

2. 백엔드 병렬처리 최적화 분석
- 기존 가정: 병렬처리를 더 늘려야 성능 향상
- 실제 발견: Tools 노드에 ThreadPoolExecutor 이미 구현됨 (`agent_nodes.py:131-138`)
- 실제 활용도: 10-15% (LLM이 한 번에 1개 도구만 호출)
- 결론: 추가 병렬화는 효과 낮음, 다른 최적화 필요

3. 진짜 병목 지점 발견
- 임베딩 순차 처리 (70% 영향): `generate_embeddings.py`에서 11,110개 조문을 하나씩 처리 (92분 소요)
  - 해결: 배치 처리 (BATCH_SIZE=32) → 27분 (70% 개선)
- Vector Search (20-30% 영향): Supabase RPC 동기 호출, Query Expansion 중복 임베딩
- LLM API (15-25% 영향): Rate Limit 보호 없음

4. 병렬처리 위험 요소 발견
- Gemini API Rate Limit (높음): 재시도 로직 없음 → 부하 시 전체 실패
- Supabase 연결 풀 고갈 (중간): 타임아웃 미설정 → ThreadPool 사용 시 연결 경쟁
- VectorSearch 상태 오염 (중간): `last_results` 멀티스레드 안전성 없음
- 결론: 무리하게 병렬처리 늘리면 위험

5. 권장 개선사항 (우선순위별)
- 즉시: 임베딩 배치화 (70% 시간 단축), Gemini API 재시도 로직 (tenacity)
- 중기: Supabase 타임아웃/재시도, VectorSearch 스레드 안전성 (threading.Lock)
- 보류: 비동기 I/O 도입, Agent 로직 최적화 (효과 대비 개발 노력 높음)

**최종 판단**: 병렬처리 확장보다 임베딩 배치화와 API 안정성 개선 우선
**상세 분석**: `C:\Users\inc02\.claude\plans\dynamic-swinging-crane.md`


## 2025.12.14
1. sementic search만으로는 정확한 문서 판별을 할 수 없을 것 같다고 판단 BM25와 metadata 키워드 서치 도입 고려
2. db검토 결과 일부 db에서 조문 제목 이외에 본문이 포함되어있지 않은 data가 다수 존재하여 해당 부분을 확인하고 re-embedding 진행
3. 애매한 예외조항 (예: 대통령령이 정한 바에 따라...)을 처리하기 위해 시행령과 시행규칙을 db에 추가 후 추가 search시 해당 법령 서치하는 방안