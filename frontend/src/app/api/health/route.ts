/**
 * Next.js API Route: /api/health
 * 백엔드 Health Check
 */

import { NextResponse } from 'next/server';

const API_URL = process.env.NEXT_PUBLIC_API_URL;
const HF_TOKEN = process.env.HF_TOKEN;

export async function GET() {
  try {
    const response = await fetch(`${API_URL}/health`, {
      headers: {
        'Authorization': `Bearer ${HF_TOKEN}`,
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { status: 'unhealthy' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('Health check error:', error);
    return NextResponse.json(
      { status: 'unhealthy' },
      { status: 500 }
    );
  }
}
