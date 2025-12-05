import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { StatsProvider } from "@/contexts/StatsContext";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "한국 법령 챗봇 - Lawbot KR",
  description: "AI 기반 한국 법령 상담 챗봇. 법률 질문에 대한 빠르고 정확한 답변을 제공합니다.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <StatsProvider>
          {children}
        </StatsProvider>
      </body>
    </html>
  );
}
