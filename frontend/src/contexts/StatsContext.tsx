'use client';

import { createContext, useContext, useState, ReactNode } from 'react';

interface Stats {
  totalQuestions: number;
  averageResponseTime: number;
  successRate: number;
  totalResponseTime: number;
}

interface StatsContextType {
  stats: Stats;
  updateStats: (responseTime: number, isSuccess: boolean) => void;
}

const StatsContext = createContext<StatsContextType | undefined>(undefined);

export function StatsProvider({ children }: { children: ReactNode }) {
  const [stats, setStats] = useState<Stats>({
    totalQuestions: 0,
    averageResponseTime: 0,
    successRate: 100,
    totalResponseTime: 0,
  });

  const updateStats = (responseTime: number, isSuccess: boolean) => {
    setStats((prev) => {
      const newTotalQuestions = prev.totalQuestions + 1;
      const newTotalResponseTime = prev.totalResponseTime + responseTime;
      const newAverageResponseTime = newTotalResponseTime / newTotalQuestions;

      const successCount = Math.round((prev.successRate / 100) * prev.totalQuestions) + (isSuccess ? 1 : 0);
      const newSuccessRate = (successCount / newTotalQuestions) * 100;

      return {
        totalQuestions: newTotalQuestions,
        averageResponseTime: newAverageResponseTime,
        successRate: newSuccessRate,
        totalResponseTime: newTotalResponseTime,
      };
    });
  };

  return (
    <StatsContext.Provider value={{ stats, updateStats }}>
      {children}
    </StatsContext.Provider>
  );
}

export function useStats() {
  const context = useContext(StatsContext);
  if (context === undefined) {
    throw new Error('useStats must be used within a StatsProvider');
  }
  return context;
}
