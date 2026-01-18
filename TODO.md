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

3. LLM 전략
- 모델: Gemini 2.5 Flash (Tool calling 및 답변 생성)
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
- 도구호출과 generating의 역할을 나누어 중복전송이나 꼬임을 방지

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


## 2025.12.14
1. sementic search만으로는 정확한 문서 판별을 할 수 없을 것 같다고 판단 BM25와 metadata 키워드 서치 도입 고려
2. db검토 결과 일부 db에서 조문 제목 이외에 본문이 포함되어있지 않은 data가 다수 존재하여 해당 부분을 확인하고 re-embedding 진행
3. 애매한 예외조항 (예: 대통령령이 정한 바에 따라...)을 처리하기 위해 시행령과 시행규칙을 db에 추가 후 추가 search시 해당 법령 서치하는 방안

## 2025.12.16
1. 별표/별지 조회 유틸 추가
- backend/src/law_api.py에 MST 조회/별표 HTML·JSON 스니펫 함수 추가(`_find_mst_for_byeol`, `list_byeol`, `get_byeol_html/json`, `fetch_byeol`)
- 에이전트 툴로 `search_byeol` 추가, 프롬프트에 `byeol_to_search` 필드 반영

2. 반복 도구 호출 방지
- Agent 상태에 `exceptions_checked` 플래그 추가 (agent_state.py)
- agent_nodes.py에서 `check_exceptions_needed`를 1회만 허용하도록 필터링, 상태 전달
- agent_streaming.py 초기 상태에 플래그 추가

3. 테스트 경로/기대값 정리
- tests/conftest.py에서 backend 경로를 sys.path에 추가해 `src.*` 임포트 오류 해결
- tests/test_agentic_rag.py 툴 개수 5개로 수정, tests/test_tools.py 유사도 포맷 수정
- tests/test_law_api.py 조문번호 포맷(6자리) 및 데이터 구조/메시지 검증 수정


## 2025.12.29
1. 코드베이스 전체 점검 및 개선사항 도출
- 현재 시스템: 벡터검색 → 예외조항 체크 → 추가검색 → LLM 답변 → DB 저장 (평균 7-18초)
- 기본 기능은 잘 작동하지만 운영 안정성 강화 필요

2. 안정성 개선 계획 (이번주)
- API 안정성 강화: tenacity로 재시도 로직 추가 (Rate Limit 대응)
- 스트리밍 안정화: agent_streaming.py 에러 핸들링 강화
- 동시성 안전성: vector_search.py threading.Lock 추가 (동시 요청 처리)
- DB 품질 개선: generate_embeddings.py 검증 로직 추가 및 재임베딩
- Supabase 안정성: 타임아웃 설정으로 무한 대기 방지
- 앱 로딩 속도 개선: BM25 인덱스 백그라운드 빌드로 시작 시간 단축

3. 성능 최적화 계획 (다음주)
- Query Expansion 효율화: LLM 호출 및 임베딩 생성 중복 제거
- 동시성 최적화: ThreadPool max_workers 조정 (8 → 3)
- 로깅 표준화: 일관된 에러 메시지 형식

4. 추가 기능 계획 (이후)
- 캐싱 시스템: lru_cache로 조문/판례 API 호출 최적화
- 벡터 검색 최적화: 재정렬 후보 수 조정 (top_k*6 → top_k*2)
- 테스트 강화: 통합 테스트 추가

5. 작업 일정
**12/29:**
- ✅ BM25 백그라운드 로딩 (app.py:22, background=True로 변경)
- ✅ API 재시도 로직 추가 완료
  - config.py: llm_invoke_with_retry, llm_stream_with_retry 함수 추가
  - agentic_rag.py: Query Expansion 및 check_exceptions_needed에 적용
  - vector_search.py: 서브쿼리 추출에 적용
  - agent_streaming.py: 스트리밍 답변 생성에 적용
  - 재시도 정책: 최대 3회, 지수 백오프 (2초 → 4초 → 8초)
- ✅ 근거 법령 미표시 문제 해결
  - 원인: LLM이 ToolMessage 내용에서 근거 추출 방법을 모름
  - 해결: agent_streaming.py 프롬프트 명확화 (도구 결과 확인 방법 단계별 지시)
  - MCP 구조 재평가: 현재 불필요, 프롬프트 개선으로 충분
- ✅ **평가 메트릭 시스템 구축 완료**
  - 기존 문제: 모니터링용 로깅만 있고 평가용 메트릭 부재
  - 해결: 이중 로깅 전략 도입
    1. 운영 모니터링 (wandb_logger.py): 실시간 성능 추적
    2. 평가 메트릭 (evaluation_metrics.py): 실험 비교용
  - 신규 파일:
    - backend/src/monitoring/evaluation_metrics.py: R@k, MRR, NDCG, Citation F1, Faithfulness 등
    - backend/src/monitoring/evaluator.py: 오프라인 배치 평가 실행기
    - datasets/eval_questions.json: 평가용 질문 10개 (카테고리별 분류)
    - datasets/ground_truth.json: 정답 조문 레이블링 (수동)
    - datasets/README.md: 데이터셋 사용법 및 메트릭 설명
  - 평가 메트릭 종류:
    - Retrieval: Recall@3, Recall@5, MRR, NDCG@3
    - Citation: Precision, Recall, F1 (답변에 근거 법령 표시율)
    - Quality: Faithfulness, Relevance, Completeness (LLM 기반 평가)
    - Cost & Latency: response_time_ms, total_tokens, api_calls
  - 다음 단계: AgenticRAG에 평가 모드 추가 (vanilla, current, full_self_rag)
- ✅ **Ground Truth 법령 조문 내용 자동 수집 완료**
  - 문제 발견: ground_truth.json의 context 필드가 API 검증 없이 임의 작성됨
  - 해결: 실제 법령 API로 조문 내용 자동 수집
  - 신규 파일:
    - scripts/collect_article_content.py: 법령 조문 내용 자동 수집 스크립트
  - 수집 결과:
    - 14개 조문 모두 수집 완료 (성공률 100%)
    - 예시: "민법 750" → "제750조(불법행위의 내용) 고의 또는 과실로..."
  - ground_truth.json 구조 변경:
    - 삭제: context 필드 (임의 작성 내용)
    - 추가: article_content 필드 (API 검증된 실제 조문 내용)
  - 용도: Faithfulness 평가 시 "정확한 법령 내용" 기준으로 사용
  - Windows 콘솔 인코딩 이슈 해결 (cp949 → utf-8)

**12/30:**
- ✅ AgenticRAG 평가 모드 구현 (mode 파라미터 추가)
  - vanilla, current, self_rag 모드 구현
  - run_with_metrics() 메서드 추가 (retrieved_docs, metrics 반환)
- ⏸️ Supabase 타임아웃 설정 (SDK 미지원으로 보류)

**12/31:**
- ✅ 멀티스레드 안전성 강화 (threading.Lock)
  - vector_search.py에 _results_lock 추가
  - agentic_rag.py의 _get_last_search_results() 스레드 안전 처리
- ⏸️ 스트리밍 에러 핸들링 (복잡도 대비 가치 낮아 보류)
- ✅ **예외 케이스 집중 실험 완료**
  - 5개 질문 (q011~q015) × 3개 모드 (vanilla, current, self_rag)
  - 실험 결과: Current 모드 100% 정확도, Self-RAG 80% 정확도
  - **결론: Current 모드 채택, Self-RAG 서비스 배포 제외**
  - 문서화: docs/EXPERIMENT_RESULTS.md

**1/1:**
- ✅ 프론트엔드 UI/UX 검토 완료
  - 현재 상태: Next.js + React 스트리밍 UI, 반응형 디자인 완성도 높음
  - 발견한 개선점:
    - P0 (필수): 에러 처리 개선, 사용자 피드백 기능, 법령 출처 표시, 채팅 히스토리 저장
    - P1 (중요): 로딩 상태 개선, 답변 복사 기능, 모바일 UX 개선
    - P2 (선택): 실시간 통계 연동, 접근성 개선, 성능 최적화
  - 결론: 서비스 기본 동작은 완성됨, 사용자 경험 향상 개선점 문서화

**1/2:**
- ✅ **프론트엔드 P0 UI/UX 개선 완료**
  - 에러 처리 개선: 네트워크/타임아웃/서버 에러 분류, 재시도 버튼
  - 사용자 피드백: 👍/👎 버튼, Supabase 저장, /api/feedback 엔드포인트
  - 법령 출처 표시: 참조 법령 배지, 국가법령정보센터 링크, answer_complete SSE 이벤트
  - 채팅 히스토리: localStorage 세션별 저장, 새로고침 복구
- ✅ **백엔드 피드백 및 법령 출처 API 추가**
  - POST /feedback: Supabase user_feedback 테이블 저장
  - answer_complete 이벤트: law_references 배열 전송 (중복 제거, 상위 5개)
- 다음: DB 품질 검증 로직 추가, 재임베딩 준비

6. ✅ 실험 결과

**실험 요약**:
- 5개 예외 케이스 질문으로 Vanilla, Current, Self-RAG 비교
- **결론**: Current 모드 채택 결정

**실험 결과**:
| 모드 | 평균 응답시간 | 정확률 | 비고 |
|------|--------------|--------|------|
| Vanilla | 14.4초 | 80% (4/5) | 빠르지만 예외 조항 놓침 |
| **Current** | **22.5초** | **100% (5/5)** | ✅ **최적 균형** |
| Self-RAG | 80.7초 | 80% (4/5) | 느리고 오답 발생 |

**핵심 발견**:
- Self-RAG는 법률 도메인에서 오히려 혼란 야기 (Q011: 제11조 과신으로 완전 반대 답변)
- Current 모드의 check_exceptions_needed 휴리스틱이 LLM 평가보다 안정적
- 문서: docs/EXPERIMENT_RESULTS.md

**향후 계획**:
- Self-RAG 코드는 포트폴리오/논문용으로 보존
- 서비스는 Current 모드로 배포

7. 향후 방향성
- ✅ 최종 아키텍처: Current 모드 (예외 조항 체크) 확정
- ❌ Self-RAG/CRAG: 법률 도메인에서 비효율적, 서비스 배포 제외
- 버퍼 메모리: 안정성 개선 완료 후 추가 예정
- 사용자 식별: LocalStorage 기반 user_id 저장 방식 검토
- 아키텍처: 현재 단일 도메인 특화 시스템으로 MCP 전환 불필요

8. 프론트엔드 개선 TODO (우선순위별)

**P0 (필수 - 서비스 품질 직결)** ✅ 완료
- [x] 에러 처리 개선 (재시도 버튼, 구체적 에러 메시지)
- [x] 사용자 피드백 기능 (👍/👎 버튼, Supabase 저장)
- [x] 법령 출처 표시 (답변 근거 명확화)
- [x] 채팅 히스토리 저장 (localStorage, 새로고침 대응)

**P1 (중요 - UX 개선)**
- [ ] 로딩 상태 개선 (단계별 진행 표시)
- [ ] 답변 복사 기능 (클립보드 복사)
- [ ] 모바일 UX 개선 (Auto-resize textarea)

**P2 (선택 - 추가 가치)**
- [ ] 실시간 통계 연동 (Supabase)
- [ ] 접근성 개선 (ARIA, 키보드 네비게이션)
- [ ] 성능 최적화 (React.memo)

---

## 2025.01.07
1. ✅ Buffer Memory 프롬프트 엔지니어링
- 문제: Memory 저장/로드는 되지만 LLM이 이전 내용 반복 설명
- 해결: agent_streaming.py + agentic_rag.py 프롬프트 수정
  - "이미 설명한 내용은 반복하지 마세요. 새로운 질문에만 집중하세요."
  - 구체적 예시 추가 (야근수당/주휴수당 케이스)
- 효과: 연속 대화 시 간결한 답변 기대

2. ✅ 포트폴리오 문서 개선
- portfolio_guide.md 전면 개편
- 변경: 전문가스러운 표현 → 5개월 신입이 실제로 말할 수 있는 수준
- 추가 섹션:
  - 기술 용어 쉽게 설명하기 (RAG, Hybrid Search 등)
  - 절대 하지 말아야 할 실수 (과장, 거짓)
  - 면접 전날 체크리스트
  - 마지막 조언 (모르면 모른다고 하기)

3. ✅ .gitignore 정리
- 개인 면접 준비 문서 추가:
  - docs/portfolio_guide.md
  - docs/evaluation_results.md
  - docs/search_quality_improvement_plan.md
  - docs/buffer_memory.md
- 테스트 파일 추가: test_*.py, run_*.py
- 로그 파일 추가: *.log, DEBUG/
- 이유: 공개하면 오히려 역효과 (한계 노출, 면접 답변 스크립트)

4. ✅ 불필요한 파일 정리
- 삭제한 파일:
  - 모든 *.log 파일 (6개 평가 로그 포함)
  - 모든 __pycache__ 디렉토리
  - 모든 *.pyc 파일
  - run_evaluation.py, test_evaluation_modes.py
  - DEBUG/ 디렉토리 (벡터 DB 재구축 로그)
- 남겨야 할 파일:
  - test_buffer_memory.py는 삭제 예정 (.gitignore 추가됨)

5. 📝 TODO.md 업데이트
- 기존 기록 전체 보존 (개발 과정 역사)
- 이 섹션 추가 (1/7 작업 내용)

---

## 📊 프로젝트 최종 현황 (2025.01.07)

### 완료된 주요 기능
- ✅ Agentic RAG (Current 모드, 정확도 100%, 평균 응답시간 14초)
- ✅ Buffer Memory (프롬프트 엔지니어링 완료)
- ✅ 정량 평가 시스템 (Recall@5: 70%)
- ✅ 프론트엔드 P0 개선 (에러 처리, 피드백, 법령 출처)
- ✅ 포트폴리오 문서화 (면접 가이드 포함)

### 포트폴리오 제출 준비 완료
- ✅ README 최적화
- ✅ 아키텍처 문서 (docs/architecture.md)
- ✅ .gitignore 정리 (개인 문서 비공개)
- ⏸️ 배포 (선택 사항)

---

## 2025.01.15

### 1. ✅ BM25 인덱스 초기화 문제 해결
- **문제**: HuggingFace 로그에서 "BM25 검색을 건너뜁니다" 발생, Hybrid Search 결과 `semantic 15개, bm25 0개`
- **원인**: `api/main.py` startup 이벤트에서 임베딩 모델만 preload, BM25 인덱스는 lazy loading으로 첫 요청 시 빈 결과 반환
- **해결**: `api/main.py`에 `preload_bm25_index(background=False)` 추가
- **결과**: Hybrid Search 정상 작동 (`semantic 15개, bm25 15개`)

### 2. ✅ 프론트엔드 스트리밍 안됨 문제 해결
- **문제**: 백엔드에서 38개 청크 정상 생성되지만 프론트엔드에서 아무것도 수신 못함
- **원인**: `api/main.py`의 `/chat/stream` 엔드포인트에서 SSE 이벤트 **이중 래핑**
  - `agent_streaming.py`: `data: {"type": "answer_chunk", "text": "..."}\n\n` 형식으로 반환
  - `api/main.py`: 다시 `data: {"chunk": "data: {...}", "done": false}\n\n`로 감싸서 전송
  - 프론트엔드는 `{"type": "answer_chunk"}` 형식을 기대하므로 파싱 실패
- **해결**: `api/main.py`에서 agent 출력을 그대로 전달하도록 수정
  ```python
  for sse_chunk in agent_instance.run_stream(request.question, session_id=session_id):
      yield sse_chunk  # 이중 래핑 제거
  ```
- **결과**: 프론트엔드 스트리밍 정상 작동

### 3. ✅ Gemini Thinking 모드로 인한 답변 중단 문제 해결
- **문제**: `max_output_tokens=512` 설정했지만 답변이 한 문장에서 끊김
  - 로그: `output_tokens: 508, output_token_details: {'reasoning': 487}, finish_reason: 'MAX_TOKENS'`
  - 512 토큰 중 487개가 thinking(reasoning)에 소비, 실제 답변은 21토큰만
- **원인**: Gemini 2.5 Flash의 thinking 모드가 기본 활성화, `max_output_tokens`에 thinking 토큰 포함
- **해결**: `config.py`에 `thinking_budget=0` 추가 (LangChain 3.2.0에서 지원)
  ```python
  ChatGoogleGenerativeAI(
      model="gemini-2.5-flash",
      temperature=0.0,
      thinking_budget=0,  # Thinking 모드 비활성화
  )
  ```
- **결과**: reasoning 토큰 소비 없이 전체 토큰을 답변에 사용

### 4. ✅ 연계 질문 시 tool 호출 문자열 출력 문제 해결
- **문제**: 두 번째 질문("5인 미만 사업장인데도?")에서 답변 대신 `search_vector_db(query='5인 미만 사업장 부당해고')` 출력
- **원인**: 답변 생성 메시지에 이전 AI 메시지(긴 마크다운 형식)와 빈 AI 메시지가 포함되어 LLM이 혼란
- **해결**: `agent_streaming.py` 메시지 필터링 로직 전면 개편
  - 이전 대화는 `[이전 대화 맥락]` 태그로 요약 전달 (200자 제한)
  - 현재 세션에서 Human과 Tool 메시지만 추출
  - AI 메시지 완전 제거 (tool_calls 여부 무관)
  - 프롬프트에 "search_vector_db() 같은 함수 호출 출력 금지" 명시
  - 연계 질문 fewshot 예시 추가
- **결과**: 연계 질문에서도 정상적인 자연어 답변 생성

### 5. ✅ max_tokens 제한 제거
- **문제**: 복잡한 법률 질문(5인 미만 + 육아휴직 + 부당해고)에서 답변이 중간에 잘림
  - "대한법률구조공단: 경제적 어려움이 있다면 대한법률구조공단의 무료 법" 에서 끊김
- **원인**: `max_tokens=1024` 제한, 복잡한 질문은 여러 법령 인용 필요
- **결정**: 법률 도메인 특성상 정확도가 속도보다 중요, 잘린 답변은 불완전한 정보 제공
- **해결**: `max_tokens` 제한 제거, `thinking_budget=0`만 유지
- **결과**: 답변 중단 없이 완전한 법률 정보 제공

### 6. 📊 성능 현황
- **평균 응답 시간**: 21.4초 (3개 질문 기준)
- **병목 지점**: 벡터 검색 12초+ (서브쿼리 4개 × 15개 결과)
- **판단**: 법률 도메인에서 정확도 > 속도
  - 복잡한 법률 질문은 근로기준법 + 시행령 + 시행규칙 + 판례 교차 참조 필요
  - "5인 미만 사업장"처럼 예외 조항이 많아 다양한 관점 검색 필수
  - 틀린 법률 정보는 실제 피해로 이어질 수 있음
- **포트폴리오 관점**: "왜 21초가 걸리는가"를 설명할 수 있으면 강점
  - Hybrid Search (Semantic + BM25)
  - Multi-query 전략
  - 판례 연동

### 7. 수정된 파일 목록
| 파일 | 변경 내용 |
|------|----------|
| `api/main.py` | BM25 preload 추가, SSE 이중 래핑 제거 |
| `backend/src/config.py` | `thinking_budget=0` 추가, `max_tokens` 제거 |
| `backend/src/agent_streaming.py` | 메시지 필터링 로직 개편, 프롬프트 개선 |
| `frontend/.env.local` | 로컬 개발용 환경변수 설정 |

### 8. 남은 작업
- [ ] HuggingFace Spaces 배포 후 실제 환경 테스트
- [ ] 프롬프트 튜닝 (300자 이내 권장사항 준수 여부 모니터링)
- [ ] 로컬 테스트 자동화 스크립트 작성