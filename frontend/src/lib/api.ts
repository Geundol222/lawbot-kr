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

/**
 * Chat API 호출 (Streaming)
 */
export async function chatStreamAPI(
  request: ChatRequest,
  onChunk: (chunk: string) => void,
  onDone?: (sessionId: string) => void,
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

    while (true) {
      const { done, value } = await reader.read();

      if (done) break;

      // 디코드하고 버퍼에 추가
      buffer += decoder.decode(value, { stream: true });

      // SSE 이벤트 파싱 (data: 로 시작하는 줄)
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // 마지막 불완전한 줄은 버퍼에 유지

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));

            if (data.error) {
              onError?.(data.error);
              return;
            }

            if (data.chunk) {
              onChunk(data.chunk);
            }

            if (data.done) {
              onDone?.(data.session_id);
              return;
            }
          } catch (e) {
            console.error('Failed to parse SSE data:', e);
          }
        }
      }
    }
  } catch (error) {
    onError?.(error instanceof Error ? error.message : 'Unknown error');
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
