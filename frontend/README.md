# Lawbot-KR Frontend

Next.js 기반 한국 법령 챗봇 웹 인터페이스

## 🚀 로컬 개발

### 1. 의존성 설치

```bash
cd frontend
npm install
```

### 2. 환경변수 설정

`.env.local` 파일이 이미 생성되어 있습니다:

```env
NEXT_PUBLIC_API_URL=https://geundol222-lawbot-kr.hf.space
HF_TOKEN=hf_YOUR_TOKEN
```

### 3. 개발 서버 실행

```bash
npm run dev
```

브라우저에서 http://localhost:3000 접속

---

## 📁 주요 파일

- `src/app/page.tsx` - 메인 페이지
- `src/components/ChatInterface.tsx` - 채팅 UI
- `src/lib/api.ts` - API 클라이언트
- `src/app/api/chat/route.ts` - Chat API Route (서버사이드)
- `.env.local` - 환경변수

---

## 🚀 Vercel 배포

1. GitHub에 Push
2. Vercel에서 Import
3. Environment Variables 설정
4. Deploy
