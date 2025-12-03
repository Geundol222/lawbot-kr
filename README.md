# ⚖️ Lawbot-KR

> 한국 법령 AI 챗봇 - 국가법령정보센터 API 기반 법률 상담 서비스

## 📋 프로젝트 개요

Lawbot-KR은 한국의 법령 정보를 실시간으로 검색하고, 사용자의 법률 질문에 답변하는 AI 챗봇입니다. 
Google Gemini LLM과 국가법령정보센터 Open API를 활용하여 정확한 법령 조문을 제공하고, 
상황별 관련 법령을 추천합니다.

## ✨ 주요 기능

### 🎯 핵심 기능
- **구체적 조문 검색**: "민법 제750조 알려줘" → 정확한 조문 내용 반환
- **상황별 법령 추천**: "회사가 야근수당 안 주는데?" → 관련 법령(근로기준법) 찾기
- **대화형 인터페이스**: 자연스러운 한국어 질의응답
- **실시간 법령 조회**: 최신 시행 법령 정보 제공

### 🔧 기술적 특징
- **LangChain Function Calling**: 질문 유형에 따른 자동 도구 선택
- **동적 API 연동**: 법령 검색 → MST 추출 → 조문 조회 자동화
- **세션 기반 히스토리**: 사용자별 대화 맥락 유지 (예정)
- **Full-Text Search**: PostgreSQL 기반 과거 대화 검색 (예정)

## 🏗️ 시스템 아키텍처
```
사용자
  ↓
Frontend (Next.js + Vercel)
  ↓
Backend API (FastAPI + Render)
  ↓
├─→ Google Gemini 2.0 Flash (LLM)
├─→ 국가법령정보센터 API (법령 데이터)
└─→ Supabase (대화 히스토리, 캐시)
```

## 🛠️ 기술 스택

### Backend
- **Framework**: FastAPI
- **LLM**: Google Gemini 2.5 Flash (via LangChain)
- **Database**: Supabase (PostgreSQL)
- **API Integration**: 
  - 국가법령정보센터 Open API
  - LangChain Tools & Function Calling

### Frontend (예정)
- **Framework**: Next.js 14
- **UI Library**: shadcn/ui
- **Styling**: Tailwind CSS

### Infrastructure
- **Backend Hosting**: Render
- **Frontend Hosting**: Vercel
- **Database**: Supabase Cloud

## 📊 데이터 플로우

### 1. 구체적 조문 질문
```
사용자: "민법 제750조 알려줘"
  ↓
LLM: get_specific_law_article(law_name="민법", article="제750조")
  ↓
법령 검색 API → MST 추출 (265307)
  ↓
조문 조회 API → JO 파라미터 (075000)
  ↓
응답: "민법 제750조(불법행위의 내용) 고의 또는 과실로 인한..."
```

### 2. 상황 기반 질문
```
사용자: "회사가 야근수당 안 주는데?"
  ↓
LLM: search_law_by_situation(situation="야근수당 안 줘")
  ↓
LLM 키워드 추출: ["근로기준법"]
  ↓
법령 검색 API → 정확한 매칭 필터링
  ↓
응답: "근로기준법 관련입니다. 근로기준법 제56조를 참고하세요."
```

## 🗂️ 프로젝트 구조
```
lawbot-kr/
├── backend/                # FastAPI 백엔드
│   ├── main.py            # FastAPI 앱
│   ├── src/
│   │   ├── agent.py       # LangChain Agent
│   │   ├── law_api.py     # 법령 API 연동
│   │   ├── law_tools.py   # LangChain Tools
│   │   ├── config.py      # 설정 & LLM
│   │   └── supabase_client.py  # DB 연동
│   └── requirements.txt
│
├── frontend/              # Next.js 프론트엔드 (예정)
│   ├── app/
│   ├── components/
│   └── lib/
│
├── app.py                 # Streamlit UI (개발용)
├── .env.example          # 환경변수 예시
└── README.md
```

## 🚀 빠른 시작

### 사전 요구사항
- Python 3.12+
- Google Gemini API Key
- 국가법령정보센터 Open API OC (이메일 ID)

### 설치 및 실행

1. **저장소 클론**
```bash
git clone https://github.com/username/lawbot-kr.git
cd lawbot-kr
```

2. **가상환경 설정**
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

3. **패키지 설치**
```bash
pip install -r requirements.txt
```

4. **환경변수 설정**
```bash
cp .env.example .env
# .env 파일 편집하여 API 키 입력
```

5. **Streamlit UI 실행**
```bash
streamlit run app.py
```

## 🔑 환경변수 설정
```env
# Google Gemini API
GOOGLE_API_KEY=your_gemini_api_key

# 법령 API
LAW_API_SERVICE=http://www.law.go.kr/DRF/lawService.do
LAW_API_SEARCH=http://www.law.go.kr/DRF/lawSearch.do
LAW_API_OC=your_email_id

# Supabase (선택)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
```

## 📖 사용 예시

### 구체적 조문 질문
```
Q: 헌법 제1조 1항이 뭐야?
A: 헌법 제1조 1항은 "대한민국은 민주공화국이다." 입니다.

Q: 민법 제750조 알려줘
A: 민법 제750조(불법행위의 내용)
   고의 또는 과실로 인한 위법행위로 타인에게 손해를 가한 자는 
   그 손해를 배상할 책임이 있다.
```

### 상황 기반 질문
```
Q: 회사가 야근수당 안 주는데?
A: 회사가 야근수당을 지급하지 않는 것은 근로기준법 위반에 해당할 수 있습니다.
   근로기준법 제56조를 참고하세요.

Q: 월세 계약 해지하고 싶어
A: 월세 계약 해지는 주택임대차보호법과 민법에 따라 처리됩니다...
```

## 🎯 로드맵

### Phase 1: 핵심 기능 구현 ✅
- [x] LangChain + Gemini Function Calling
- [x] 법령 API 완전 연동
- [x] 구체적 조문 vs 상황 질문 분류
- [x] Streamlit 로컬 UI

### Phase 2: 인프라 구축 🚧
- [ ] Supabase 테이블 설계
- [ ] FastAPI 백엔드 API
- [ ] 세션 기반 대화 히스토리
- [ ] Render 배포

### Phase 3: 프론트엔드 🔜
- [ ] Next.js UI 개발
- [ ] 실시간 채팅 인터페이스
- [ ] Vercel 배포

### Phase 4: 고도화 🔮
- [ ] 대화 히스토리 기반 컨텍스트 활용
- [ ] Full-Text Search (과거 대화 검색)
- [ ] 자주 찾는 법령 캐싱
- [ ] 통계 및 분석 대시보드

## ⚠️ 주의사항

- 본 챗봇은 **법률 정보 제공 목적**이며, 정식 법률 자문이 아닙니다.
- 중요한 법률 문제는 반드시 변호사 등 전문가와 상담하시기 바랍니다.
- 제공되는 법령 정보는 국가법령정보센터 API 기준이며, 최신 개정 사항을 확인하세요.

## 📝 라이선스

MIT License

## 👨‍💻 개발자

- GitHub: [@username](https://github.com/username)
- Email: your.email@example.com

## 🙏 감사의 말

- [국가법령정보센터](https://www.law.go.kr) - 법령 API 제공
- [LangChain](https://langchain.com) - LLM 프레임워크
- [Google Gemini](https://ai.google.dev) - LLM API

---

**Made with ❤️ for Korean Legal Information Accessibility**