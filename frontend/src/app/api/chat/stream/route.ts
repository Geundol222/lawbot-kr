/**
 * Next.js API Route: /api/chat/stream
 * 스트리밍 응답을 위한 엔드포인트
 */

import { NextRequest } from 'next/server';

const API_URL = process.env.NEXT_PUBLIC_API_URL;
const HF_TOKEN = process.env.HF_TOKEN;

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // HF Spaces API 호출 (스트리밍)
    const response = await fetch(`${API_URL}/chat/stream`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${HF_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return new Response(
        JSON.stringify({ detail: error.detail || 'Backend API error' }),
        {
          status: response.status,
          headers: { 'Content-Type': 'application/json' }
        }
      );
    }

    // SSE 스트림을 그대로 전달
    return new Response(response.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });

  } catch (error) {
    console.error('Chat Stream API error:', error);
    return new Response(
      JSON.stringify({ detail: 'Internal Server Error' }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' }
      }
    );
  }
}
