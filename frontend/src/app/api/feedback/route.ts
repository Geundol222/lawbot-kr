/**
 * Next.js API Route: /api/feedback
 * 사용자 피드백을 Supabase에 저장
 */

import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.NEXT_PUBLIC_API_URL;
const HF_TOKEN = process.env.HF_TOKEN;

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // HF Spaces API 호출 (피드백 저장)
    const response = await fetch(`${API_URL}/feedback`, {
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

    return NextResponse.json({ success: true });

  } catch (error) {
    console.error('Feedback API error:', error);
    return NextResponse.json(
      { detail: 'Internal Server Error' },
      { status: 500 }
    );
  }
}
