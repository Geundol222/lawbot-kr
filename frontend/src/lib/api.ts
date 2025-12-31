/**
 * API 클라이언트
 * Hugging Face Spaces 백엔드와 통신
 */

export interface ChatRequest {
  question: string;
  session_id?: string;
}

export interface ChatResponse {
  answer: string;
  session_id: string;
}

export interface HealthResponse {
  status: string;
}

/**
 * Chat API 호출 (Non-streaming, 하위 호환용)
 */
export async function chatAPI(request: ChatRequest): Promise<ChatResponse> {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API Error: ${response.status}`);
  }

  return response.json();
}

export interface SSEEvent {
  type: 'searching' | 'checking_exceptions' | 'answer_start' | 'answer_chunk' | 'answer_complete' | 'error';
  message?: string;
  text?: string;
  articles?: string[];
  reason?: string;
  law_references?: Array<{ law_name: string; article: string }>;
}

export interface FeedbackRequest {
  session_id: string;
  message_index: number;
  feedback_type: 'positive' | 'negative';
  message_content: string;
}

/**
 * Chat API 호출 (Streaming with multiple event types)
 */
export async function chatStreamAPI(
  request: ChatRequest,
  onSearching?: () => void,
  onCheckingExceptions?: (articles: string[], reason: string) => void,
  onAnswerChunk?: (chunk: string) => void,
  onDone?: (lawReferences?: Array<{ law_name: string; article: string }>) => void,
  onError?: (error: string) => void
): Promise<void> {
  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';
    let lawReferences: Array<{ law_name: string; article: string }> | undefined;

    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        onDone?.(lawReferences);
        break;
      }

      // 디코드하고 버퍼에 추가
      buffer += decoder.decode(value, { stream: true });

      // SSE 이벤트 파싱 (data: 로 시작하는 줄)
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // 마지막 불완전한 줄은 버퍼에 유지

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event: SSEEvent = JSON.parse(line.slice(6));

            switch (event.type) {
              case 'searching':
                onSearching?.();
                break;

              case 'checking_exceptions':
                onCheckingExceptions?.(
                  event.articles || [],
                  event.reason || ''
                );
                break;

              case 'answer_start':
                // 답변 시작 (필요시 UI 상태 변경)
                break;

              case 'answer_chunk':
                if (event.text) {
                  onAnswerChunk?.(event.text);
                }
                break;

              case 'answer_complete':
                // 답변 완료 시 법령 출처 저장
                if (event.law_references) {
                  lawReferences = event.law_references;
                }
                break;

              case 'error':
                onError?.(event.message || 'Unknown error');
                return;
            }
          } catch (e) {
            console.error('Failed to parse SSE data:', e, 'Line:', line);
          }
        }
      }
    }
  } catch (error) {
    onError?.(error instanceof Error ? error.message : 'Unknown error');
  }
}

/**
 * 사용자 피드백 전송
 */
export async function submitFeedback(feedback: FeedbackRequest): Promise<void> {
  const response = await fetch('/api/feedback', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(feedback),
  });

  if (!response.ok) {
    throw new Error(`Feedback submission failed: ${response.status}`);
  }
}

/**
 * Health Check (클라이언트에서 직접 호출)
 */
export async function healthCheck(): Promise<HealthResponse> {
  const response = await fetch('/api/health');

  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }

  return response.json();
}
