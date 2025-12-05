/**
 * Next.js API Route: /api/chat
 * HF 토큰을 서버사이드에서 처리하여 클라이언트에 노출하지 않음
 */

import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.NEXT_PUBLIC_API_URL;
const HF_TOKEN = process.env.HF_TOKEN;

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // HF Spaces API 호출 (서버사이드에서 토큰 사용)
    const response = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${HF_TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      return NextResponse.json(
        { detail: error.detail || 'Backend API error' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('Chat API error:', error);
    return NextResponse.json(
      { detail: 'Internal Server Error' },
      { status: 500 }
    );
  }
}
