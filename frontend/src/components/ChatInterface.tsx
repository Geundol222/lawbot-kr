'use client';

import { useState, useRef, useEffect } from 'react';
import { chatStreamAPI, submitFeedback } from '@/lib/api';
import { useStats } from '@/contexts/StatsContext';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: Date;
  error?: boolean;
  lawReferences?: Array<{ law_name: string; article: string }>;
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(`session-${Date.now()}`);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const { updateStats } = useStats();
  const [shouldAutoScroll, setShouldAutoScroll] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);

  // localStorage에서 히스토리 로드
  useEffect(() => {
    const savedMessages = localStorage.getItem(`chat-history-${sessionId}`);
    if (savedMessages) {
      try {
        const parsed = JSON.parse(savedMessages);
        setMessages(parsed.map((msg: Message) => ({
          ...msg,
          timestamp: msg.timestamp ? new Date(msg.timestamp) : undefined
        })));
      } catch (e) {
        console.error('Failed to load chat history:', e);
      }
    }
  }, [sessionId]);

  // 메시지 변경 시 localStorage에 저장
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem(`chat-history-${sessionId}`, JSON.stringify(messages));
    }
  }, [messages, sessionId]);

  // 사용자가 스크롤했는지 감지
  const handleScroll = () => {
    if (!messagesContainerRef.current) return;

    const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef.current;
    const isNearBottom = scrollHeight - scrollTop - clientHeight < 100;

    setShouldAutoScroll(isNearBottom);
  };

  // 메시지 자동 스크롤 (사용자가 아래에 있을 때만)
  useEffect(() => {
    if (!shouldAutoScroll) return;

    if (messagesEndRef.current && messagesContainerRef.current) {
      // 스트리밍 중에는 부드럽게, 아니면 즉시 스크롤
      const behavior = isStreaming ? 'auto' : 'smooth';
      messagesEndRef.current.scrollIntoView({ behavior, block: 'end' });
    }
  }, [messages, shouldAutoScroll, isStreaming]);

  const handleRetry = (questionToRetry: string) => {
    setInput(questionToRetry);
    // 자동으로 전송하지 않고 입력창에만 채워줌
  };

  const handleSubmit = async (e: React.FormEvent, retryQuestion?: string) => {
    e.preventDefault();
    const question = retryQuestion || input;
    if (!question.trim() || loading) return;

    if (!retryQuestion) {
      setInput('');
    }
    setLoading(true);
    setIsStreaming(true);
    setShouldAutoScroll(true); // 새 질문 시작 시 자동 스크롤 활성화

    const startTime = Date.now();

    // 사용자 메시지 + 로딩 메시지 추가
    setMessages(prev => [
      ...prev,
      {
        role: 'user',
        content: question,
        timestamp: new Date(),
      },
      {
        role: 'assistant',
        content: '📚 해당 질문에 대해 적절한 법령을 찾아보겠습니다...',
        timestamp: new Date(),
      },
    ]);

    let fullResponse = '';

    try {
      await chatStreamAPI(
        {
          question,
          session_id: sessionId,
        },
        // onSearching: 법령 검색 중
        () => {
          setMessages(prev => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = {
              role: 'assistant',
              content: '📚 법령을 검색 중입니다...',
              timestamp: new Date(),
            };
            return newMessages;
          });
        },
        // onCheckingExceptions: 예외조항 확인 중
        (articles: string[]) => {
          setMessages(prev => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = {
              role: 'assistant',
              content: `💭 예외 조항이 있는 것 같습니다. 예외 조항을 검색중입니다...\n\n확인할 조문: ${articles.join(', ')}`,
              timestamp: new Date(),
            };
            return newMessages;
          });
        },
        // onAnswerChunk: 실시간 스트리밍 (LLM에서 직접 전송)
        (chunk: string) => {
          fullResponse += chunk;

          setMessages(prev => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = {
              role: 'assistant',
              content: fullResponse + '▌',  // 커서 표시
              timestamp: new Date(),
            };
            return newMessages;
          });
        },
        // onDone: 완료
        (lawReferences) => {
          const responseTime = (Date.now() - startTime) / 1000;
          updateStats(responseTime, true);

          setMessages(prev => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = {
              role: 'assistant',
              content: fullResponse,  // 커서 제거
              timestamp: new Date(),
              lawReferences: lawReferences,  // 법령 출처 추가
            };
            return newMessages;
          });
          setLoading(false);
          setIsStreaming(false);
        },
        // onError: 에러 처리
        (error: string) => {
          console.error('Chat error:', error);
          const responseTime = (Date.now() - startTime) / 1000;
          updateStats(responseTime, false);

          // 에러 타입 분류
          let errorMessage = '죄송합니다. 일시적인 오류가 발생했습니다.';

          if (error.includes('fetch') || error.includes('network')) {
            errorMessage = '네트워크 연결에 문제가 있습니다. 인터넷 연결을 확인해주세요.';
          } else if (error.includes('timeout')) {
            errorMessage = '응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.';
          } else if (error.includes('500') || error.includes('Internal Server')) {
            errorMessage = '서버에서 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
          }

          setMessages(prev => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = {
              role: 'assistant',
              content: `❌ **${errorMessage}**\n\n오류 내용: ${error}\n\n다시 시도하시려면 아래 버튼을 눌러주세요.`,
              timestamp: new Date(),
              error: true,
            };
            return newMessages;
          });
          setLoading(false);
          setIsStreaming(false);
        }
      );
    } catch (error) {
      console.error('Unexpected error:', error);
      const responseTime = (Date.now() - startTime) / 1000;
      updateStats(responseTime, false);

      setMessages(prev => {
        const newMessages = [...prev];
        newMessages[newMessages.length - 1] = {
          role: 'assistant',
          content: '죄송합니다. 일시적인 오류가 발생했습니다.\n잠시 후 다시 시도해주세요.',
          timestamp: new Date(),
        };
        return newMessages;
      });
      setLoading(false);
      setIsStreaming(false);
    }
  };

  const exampleQuestions = [
    { icon: '⏰', text: '연장근로 수당은 얼마나 받을 수 있나요?', query: '근로기준법 제56조 연장근로 가산임금이 어떻게 되나요?' },
    { icon: '📦', text: '택배 분실 시 보상은?', query: '택배가 분실되었을 때 소비자 보호법은 어떻게 되나요?' },
    { icon: '🏢', text: '부당해고 구제 방법은?', query: '부당해고를 당했을 때 어떻게 대처해야 하나요?' },
  ];

  const handleExampleClick = (query: string) => {
    setInput(query);
  };

  return (
    <div className="flex flex-col h-full max-w-5xl lg:max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 relative">
      {/* 메시지 영역 */}
      <div
        ref={messagesContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto mb-4 sm:mb-6 space-y-4 sm:space-y-6 py-3 sm:py-4"
      >
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            {/* Welcome Section */}
            <div className="mb-8 sm:mb-12 animate-fade-in">
              <div className="inline-flex items-center justify-center w-16 h-16 sm:w-20 sm:h-20 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-2xl shadow-lg mb-5 sm:mb-6">
                <svg className="w-8 h-8 sm:w-10 sm:h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
                </svg>
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 mb-2 sm:mb-3">
                법률 질문을 입력하세요
              </h2>
              <p className="text-base sm:text-lg text-gray-600 max-w-2xl mx-auto">
                AI가 관련 법령을 찾아 정확하고 빠른 답변을 제공합니다
              </p>
            </div>

            {/* Example Questions */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4 w-full max-w-4xl">
              {exampleQuestions.map((example, idx) => (
                <button
                  key={idx}
                  onClick={() => handleExampleClick(example.query)}
                  className="group relative p-4 sm:p-6 bg-white border-2 border-gray-200 rounded-2xl hover:border-blue-400 hover:shadow-lg transition-all duration-300 text-left"
                >
                  <div className="flex items-start space-x-3">
                    <span className="text-2xl sm:text-3xl group-hover:scale-110 transition-transform duration-300">
                      {example.icon}
                    </span>
                    <div className="flex-1">
                      <p className="text-gray-900 font-medium text-sm sm:text-base group-hover:text-blue-600 transition-colors">
                        {example.text}
                      </p>
                    </div>
                  </div>
                  <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                    <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </div>
                </button>
              ))}
            </div>

            {/* Info Badge */}
            <div className="mt-12 inline-flex items-center px-4 py-2 bg-blue-50 border border-blue-200 rounded-full text-sm text-blue-700">
              <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
              Powered by Agentic RAG + Vector Search
            </div>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-slide-in`}
          >
            <div
              className={`flex items-start space-x-3 max-w-[90%] sm:max-w-[85%] ${
                msg.role === 'user' ? 'flex-row-reverse space-x-reverse' : ''
              }`}
            >
              {/* Avatar */}
              <div
                className={`flex-shrink-0 w-9 h-9 sm:w-10 sm:h-10 rounded-full flex items-center justify-center shadow-md ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-br from-blue-500 to-indigo-600'
                    : 'bg-gradient-to-br from-gray-700 to-gray-900'
                }`}
              >
                {msg.role === 'user' ? (
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
                  </svg>
                )}
              </div>

              {/* Message Content */}
              <div className="flex-1">
                <div
                  className={`rounded-2xl shadow-sm ${
                    msg.role === 'user'
                      ? 'bg-gray-100 border border-gray-300'
                      : 'bg-white border border-gray-200'
                  }`}
                >
                  <div className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold text-gray-500">
                        {msg.role === 'user' ? '사용자' : 'AI 법률 어시스턴트'}
                      </span>
                      {msg.timestamp && (
                        <span className="text-xs text-gray-400">
                          {msg.timestamp.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      )}
                    </div>
                    <div className="prose prose-sm sm:prose max-w-none leading-relaxed text-gray-900">
                      {msg.role === 'assistant' ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>
                          {msg.content}
                        </ReactMarkdown>
                      ) : (
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                      )}
                    </div>

                    {/* 법령 출처 표시 */}
                    {msg.role === 'assistant' && msg.lawReferences && msg.lawReferences.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-200">
                        <div className="flex items-start space-x-2">
                          <svg className="w-4 h-4 text-blue-600 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
                          </svg>
                          <div className="flex-1">
                            <div className="text-xs font-semibold text-gray-600 mb-1">참조 법령</div>
                            <div className="flex flex-wrap gap-2">
                              {msg.lawReferences.map((ref, i) => (
                                <a
                                  key={i}
                                  href={`https://law.go.kr/LSW/lsInfoP.do?lsiSeq=${ref.law_name}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center px-2 py-1 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-700 hover:bg-blue-100 transition-colors"
                                >
                                  <span className="font-medium">{ref.law_name}</span>
                                  {ref.article && <span className="ml-1">제{ref.article}조</span>}
                                </a>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* 액션 버튼 (assistant 메시지에만 표시) */}
                    {msg.role === 'assistant' && !msg.error && (
                      <div className="mt-3 pt-3 border-t border-gray-200 flex items-center justify-between">
                        {/* 복사 버튼 */}
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(msg.content);
                            // TODO: 복사 완료 토스트 메시지
                          }}
                          className="flex items-center space-x-1 px-2 py-1 text-xs text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded transition-colors"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                          </svg>
                          <span>복사</span>
                        </button>

                        {/* 피드백 버튼 */}
                        <div className="flex items-center space-x-1">
                          <span className="text-xs text-gray-500 mr-2">도움이 되었나요?</span>
                          <button
                            onClick={async () => {
                              try {
                                await submitFeedback({
                                  session_id: sessionId,
                                  message_index: idx,
                                  feedback_type: 'positive',
                                  message_content: msg.content,
                                });
                                // TODO: 성공 토스트 메시지
                                console.log('Positive feedback submitted');
                              } catch (error) {
                                console.error('Failed to submit feedback:', error);
                              }
                            }}
                            className="p-1 text-gray-400 hover:text-green-600 hover:bg-green-50 rounded transition-colors"
                            title="도움됨"
                          >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5" />
                            </svg>
                          </button>
                          <button
                            onClick={async () => {
                              try {
                                await submitFeedback({
                                  session_id: sessionId,
                                  message_index: idx,
                                  feedback_type: 'negative',
                                  message_content: msg.content,
                                });
                                // TODO: 성공 토스트 메시지
                                console.log('Negative feedback submitted');
                              } catch (error) {
                                console.error('Failed to submit feedback:', error);
                              }
                            }}
                            className="p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors"
                            title="도움안됨"
                          >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.096c.5 0 .905-.405.905-.904 0-.715.211-1.413.608-2.008L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    )}

                    {/* 에러 발생 시 재시도 버튼 */}
                    {msg.role === 'assistant' && msg.error && idx > 0 && messages[idx - 1].role === 'user' && (
                      <div className="mt-3 pt-3 border-t border-red-200">
                        <button
                          onClick={() => handleRetry(messages[idx - 1].content)}
                          className="w-full flex items-center justify-center space-x-2 px-4 py-2 bg-red-50 hover:bg-red-100 text-red-700 rounded-lg transition-colors font-medium"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                          </svg>
                          <span>다시 시도</span>
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start animate-slide-in">
            <div className="flex items-start space-x-3 max-w-[85%]">
              {/* Avatar */}
              <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gradient-to-br from-gray-700 to-gray-900 flex items-center justify-center shadow-md">
                <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 6l3 1m0 0l-3 9a5.002 5.002 0 006.001 0M6 7l3 9M6 7l6-2m6 2l3-1m-3 1l-3 9a5.002 5.002 0 006.001 0M18 7l3 9m-3-9l-6-2m0-2v2m0 16V5m0 16H9m3 0h3" />
                </svg>
              </div>

              {/* Loading Content */}
              <div className="flex-1">
                <div className="bg-white border border-gray-200 rounded-2xl shadow-sm p-4">
                  <div className="flex items-center space-x-3">
                    <div className="flex space-x-2">
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                      <div className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                    </div>
                    <span className="text-sm text-gray-600">답변을 생성하고 있습니다...</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 스크롤 아래로 버튼 (사용자가 위로 스크롤했을 때만 표시) */}
      {!shouldAutoScroll && messages.length > 0 && (
        <button
          onClick={() => {
            setShouldAutoScroll(true);
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
          }}
          className="fixed bottom-24 sm:bottom-28 right-6 sm:right-8 z-10 p-3 bg-blue-500 hover:bg-blue-600 text-white rounded-full shadow-lg transition-all duration-200 animate-bounce-subtle"
          aria-label="최신 메시지로 이동"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </button>
      )}

      {/* 입력 영역 */}
      <div className="border-t border-gray-200 pt-3 sm:pt-4 pb-4 bg-white/80 backdrop-blur-sm">
        <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-start">
          <div className="flex-1 relative">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
              placeholder="법률 질문을 입력하세요... (Shift+Enter로 줄바꿈)"
              rows={1}
              className="w-full px-4 py-3 pr-12 border-2 border-gray-900 bg-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none transition-all duration-200 text-gray-900 placeholder-gray-400 text-sm sm:text-base"
              disabled={loading}
              style={{
                minHeight: '48px',
                maxHeight: '120px',
              }}
            />
            {input.trim() && (
              <button
                type="button"
                onClick={() => setInput('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="h-[48px] sm:h-[52px] px-5 sm:px-6 bg-gradient-to-r from-blue-500 to-indigo-600 text-white rounded-xl hover:from-blue-600 hover:to-indigo-700 disabled:from-gray-300 disabled:to-gray-400 disabled:cursor-not-allowed transition-all duration-200 shadow-md hover:shadow-lg flex items-center justify-center space-x-2 font-medium flex-shrink-0 w-full sm:w-auto"
          >
            {loading ? (
              <>
                <svg className="animate-spin w-5 h-5" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>전송 중</span>
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
                <span>전송</span>
              </>
            )}
          </button>
        </form>

        {/* Tips */}
        <div className="mt-3 flex flex-wrap items-center justify-center text-xs text-gray-500 gap-2 sm:gap-4">
          <span className="flex items-center">
            <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            Enter로 전송
          </span>
          <span className="flex items-center">
            <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            Shift+Enter로 줄바꿈
          </span>
        </div>
      </div>
    </div>
  );
}
