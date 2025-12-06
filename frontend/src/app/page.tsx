'use client';

import ChatInterface from '@/components/ChatInterface';
import { useStats } from '@/contexts/StatsContext';

export default function Home() {
  const { stats } = useStats();
  return (
    <main className="relative min-h-screen overflow-hidden flex flex-col">
      {/* Animated Background */}
      <div className="fixed inset-0 bg-gradient-to-br from-slate-900 via-blue-900 to-indigo-900">
        {/* Animated gradient orbs */}
        <div className="absolute top-0 left-1/4 w-64 h-64 sm:w-80 sm:h-80 md:w-96 md:h-96 bg-blue-500/30 rounded-full mix-blend-multiply filter blur-3xl opacity-60 md:opacity-70 animate-blob"></div>
        <div className="absolute top-0 right-1/4 w-64 h-64 sm:w-80 sm:h-80 md:w-96 md:h-96 bg-purple-500/30 rounded-full mix-blend-multiply filter blur-3xl opacity-60 md:opacity-70 animate-blob animation-delay-2000"></div>
        <div className="absolute bottom-0 left-1/3 w-64 h-64 sm:w-80 sm:h-80 md:w-96 md:h-96 bg-indigo-500/30 rounded-full mix-blend-multiply filter blur-3xl opacity-60 md:opacity-70 animate-blob animation-delay-4000"></div>
      </div>

      {/* Content */}
      <div className="relative z-10 flex flex-col h-full">
        {/* 헤더 */}
        <header className="flex-shrink-0 backdrop-blur-xl bg-white/10 border-b border-white/20 shadow-xl">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-2 sm:py-3 lg:py-5">
            <div className="flex items-center justify-between">
              {/* 로고 및 타이틀 */}
              <div className="flex items-center space-x-4">
                <div className="relative group">
                  <div className="absolute -inset-1 bg-gradient-to-r from-blue-400 via-purple-500 to-indigo-400 rounded-2xl blur opacity-75 group-hover:opacity-100 transition duration-1000 group-hover:duration-200 animate-pulse-slow"></div>
                  <div className="relative flex items-center justify-center w-12 h-12 sm:w-14 sm:h-14 bg-gradient-to-br from-blue-500 via-purple-600 to-indigo-600 rounded-xl shadow-2xl">
                    <svg className="w-6 h-6 sm:w-7 sm:h-7 text-white animate-float" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
                    </svg>
                  </div>
                </div>
                <div>
                  <h1 className="text-xl sm:text-2xl font-black bg-gradient-to-r from-white via-blue-100 to-purple-200 bg-clip-text text-transparent drop-shadow-lg">
                    한국 법령 챗봇
                  </h1>
                  <p className="text-sm text-blue-200/90 hidden sm:block font-medium">
                    AI 기반 법률 상담 어시스턴트
                  </p>
                </div>
              </div>

              {/* 기술 스택 배지 - 더 화려하게 */}
              <div className="hidden md:flex items-center space-x-2">
                <div className="relative group">
                  <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-400 to-cyan-400 rounded-full blur opacity-75 group-hover:opacity-100 transition duration-300"></div>
                  <span className="relative px-4 py-1.5 bg-gradient-to-r from-blue-500 to-cyan-500 text-white rounded-full text-xs font-bold shadow-lg flex items-center space-x-1">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M11 3a1 1 0 10-2 0v1a1 1 0 102 0V3zM15.657 5.757a1 1 0 00-1.414-1.414l-.707.707a1 1 0 001.414 1.414l.707-.707zM18 10a1 1 0 01-1 1h-1a1 1 0 110-2h1a1 1 0 011 1zM5.05 6.464A1 1 0 106.464 5.05l-.707-.707a1 1 0 00-1.414 1.414l.707.707zM5 10a1 1 0 01-1 1H3a1 1 0 110-2h1a1 1 0 011 1zM8 16v-1h4v1a2 2 0 11-4 0zM12 14c.015-.34.208-.646.477-.859a4 4 0 10-4.954 0c.27.213.462.519.476.859h4.002z" />
                    </svg>
                    <span>Agentic RAG</span>
                  </span>
                </div>

                <div className="relative group">
                  <div className="absolute -inset-0.5 bg-gradient-to-r from-purple-400 to-pink-400 rounded-full blur opacity-75 group-hover:opacity-100 transition duration-300"></div>
                  <span className="relative px-4 py-1.5 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-full text-xs font-bold shadow-lg flex items-center space-x-1">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z" clipRule="evenodd" />
                    </svg>
                    <span>Vector Search</span>
                  </span>
                </div>

                <div className="relative group">
                  <div className="absolute -inset-0.5 bg-gradient-to-r from-orange-400 to-yellow-400 rounded-full blur opacity-75 group-hover:opacity-100 transition duration-300"></div>
                  <span className="relative px-4 py-1.5 bg-gradient-to-r from-orange-500 to-yellow-500 text-white rounded-full text-xs font-bold shadow-lg flex items-center space-x-1">
                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                    </svg>
                    <span>Gemini 2.5 Flash</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* 메인 컨텐츠 */}
        <div className="flex-1 overflow-hidden pt-4 sm:pt-6">
          <ChatInterface />
        </div>

        {/* 푸터 - 더 화려하게 */}
        <footer className="flex-shrink-0 pb-8 pt-6">
          <div className="max-w-6xl mx-auto px-4 sm:px-6">
            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              <div className="backdrop-blur-xl bg-white/10 rounded-2xl p-4 border border-white/20 hover:bg-white/20 transition-all duration-300">
                <div className="text-xl sm:text-2xl font-bold text-white">{stats.totalQuestions}+</div>
                <div className="text-[11px] sm:text-xs text-blue-200">질문 처리</div>
              </div>
              <div className="backdrop-blur-xl bg-white/10 rounded-2xl p-4 border border-white/20 hover:bg-white/20 transition-all duration-300">
                <div className="text-xl sm:text-2xl font-bold text-white">{Math.round(stats.successRate)}%</div>
                <div className="text-[11px] sm:text-xs text-blue-200">정확도</div>
              </div>
              <div className="backdrop-blur-xl bg-white/10 rounded-2xl p-4 border border-white/20 hover:bg-white/20 transition-all duration-300">
                <div className="text-xl sm:text-2xl font-bold text-white">
                  {stats.averageResponseTime > 0 ? `${stats.averageResponseTime.toFixed(1)}s` : '< 3s'}
                </div>
                <div className="text-[11px] sm:text-xs text-blue-200">평균 응답 속도</div>
              </div>
              <div className="backdrop-blur-xl bg-white/10 rounded-2xl p-4 border border-white/20 hover:bg-white/20 transition-all duration-300">
                <div className="text-xl sm:text-2xl font-bold text-white">24/7</div>
                <div className="text-[11px] sm:text-xs text-blue-200">서비스</div>
              </div>
            </div>

            {/* Links */}
            <div className="flex flex-col md:flex-row items-center justify-center space-y-4 md:space-y-0 md:space-x-8 text-sm">
              <a
                href="https://github.com/geundol222/lawbot-kr"
                target="_blank"
                rel="noopener noreferrer"
                className="group flex items-center space-x-2 text-blue-200 hover:text-white transition-all duration-300"
              >
                <div className="p-2 rounded-lg bg-white/10 group-hover:bg-white/20 transition-all duration-300">
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path fillRule="evenodd" d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z" clipRule="evenodd" />
                  </svg>
                </div>
                <span className="font-medium">GitHub 소스코드</span>
              </a>

              <span className="hidden md:block w-px h-6 bg-white/20"></span>

              <div className="flex items-center space-x-2 text-blue-200">
                <div className="p-2 rounded-lg bg-white/10">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                </div>
                <span className="font-medium">Next.js • Hugging Face • Supabase</span>
              </div>
            </div>

            {/* Disclaimer */}
            <div className="mt-8 text-center">
              <div className="inline-flex items-center px-4 py-2 backdrop-blur-xl bg-white/10 border border-white/20 rounded-full">
                <svg className="w-4 h-4 mr-2 text-yellow-300" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <span className="text-xs text-blue-100">본 챗봇은 법률 정보 제공을 목적으로 하며, 실제 법률 자문을 대체할 수 없습니다.</span>
              </div>
            </div>
          </div>
        </footer>
      </div>
    </main>
  );
}
