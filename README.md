# 한국 법령 챗봇 (Lawbot-KR)

벡터 검색과 LLM을 결합한 한국 법령 상담 챗봇입니다.

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정 (.env 파일 생성)
GOOGLE_API_KEY=your_google_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_ANON_KEY=your_supabase_key
LAW_API_SERVICE=https://www.law.go.kr/DRF/lawService.do
LAW_API_SEARCH=https://www.law.go.kr/DRF/lawSearch.do
LAW_API_OC=your_law_api_key
```

### 2. Streamlit 앱 실행

```bash
streamlit run app.py
```

또는

```bash
python3 -m streamlit run app.py
```

브라우저에서 http://localhost:8501 을 열어주세요.

### 3. CLI로 테스트

```bash
cd backend
python3 -m src.main "근로기준법 제56조가 뭐야?"
```

## 📁 프로젝트 구조

```
lawbot-kr/
├── app.py                          # Streamlit 웹 앱
├── requirements.txt                # Python 패키지
├── backend/
│   └── src/
│       ├── agentic_rag.py         # 핵심 Agent (벡터 검색 + Function Calling)
│       ├── embeddings/
│       │   └── vector_search.py   # 벡터 검색 (Supabase)
│       ├── law_api.py             # 법령 API 클라이언트
│       ├── config.py              # 설정
│       ├── main.py                # CLI 테스트
│       └── supabase_client.py     # Supabase 클라이언트
└── temp_backup/                    # 사용하지 않는 파일
```

## 🔍 작동 방식

### Agentic RAG 흐름

1. **벡터 검색 우선**: `search_vector_db`로 3,926개 임베딩된 조문 검색
2. **결과 분기**:
   - **유사도 ≥ 0.7**: `get_full_article_content`로 전체 조문 조회
   - **유사도 < 0.7**: `search_law_by_api`로 API 직접 검색
3. **답변 생성**: LLM이 조회한 법령 내용 기반으로 답변 작성

### 핵심 기술

- **LLM**: Google Gemini 2.5 Flash
- **벡터 DB**: Supabase (코사인 유사도 검색)
- **임베딩 모델**: `intfloat/multilingual-e5-large-instruct`
- **Agent 프레임워크**: LangGraph
- **API**: 국가법령정보센터 Open API

## 💬 사용 예시

### 구체적인 조문 질문
```
- 근로기준법 제56조가 뭐야?
- 민법 제750조 알려줘
- 헌법 제1조 내용
```

### 상황 설명 질문
```
- 야근수당은 얼마나 받을 수 있어?
- 회사가 야근수당 안 주는데?
- 월세 계약 해지하고 싶어
```

## 🛠️ 주요 수정 사항

### 핵심 문제 해결
- ✅ **LangGraph ToolNode 메시지 손실 문제**: 커스텀 `execute_tools`로 해결
- ✅ **Tool 중복 호출 방지**: 메시지 히스토리 유지
- ✅ **하드코딩 제거**: LLM이 자동으로 법령명 추출
- ✅ **벡터 검색 최적화**: Supabase RPC + 폴백 메커니즘

자세한 내용은 [FIXES.md](FIXES.md) 참고

## ⚠️ 주의사항

- 본 챗봇은 법률 정보 제공 목적이며, 정식 법률 자문이 아닙니다.
- 중요한 법률 문제는 반드시 전문 변호사와 상담하세요.

## 📊 데이터 출처

- **법령 데이터**: [국가법령정보센터](https://www.law.go.kr/)
- **벡터 DB**: 3,926개 주요 법령 조문 임베딩

## 🔧 문제 해결

### Streamlit이 실행되지 않을 때
```bash
pip install --upgrade streamlit
python3 -m streamlit run app.py
```

### 벡터 검색 오류 (RPC 함수 없음)
- 정상 동작: 자동으로 폴백 방식 사용
- Supabase에 `match_law_documents` 함수가 없어도 작동

## 📝 라이선스

MIT License
