"use client";

import { useState, useEffect, useCallback } from "react";
import Header from "@/components/Header";
import StatsCard from "@/components/StatsCard";
import LoadingState from "@/components/LoadingState";
import ErrorState from "@/components/ErrorState";
import {
  getAdminMetrics,
  getDashboardFull,
  getMessageTrends,
  getResponseTimeTrends,
  getDetailedHealth,
} from "@/lib/api";

export default function AdminDashboard() {
  const [metrics, setMetrics] = useState<any>(null);
  const [dashboard, setDashboard] = useState<any>(null);
  const [messageTrends, setMessageTrends] = useState<any[]>([]);
  const [responseTrends, setResponseTrends] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [metricsRes, dashRes, msgRes, respRes, healthRes] = await Promise.allSettled([
        getAdminMetrics(),
        getDashboardFull(),
        getMessageTrends(),
        getResponseTimeTrends(),
        getDetailedHealth(),
      ]);

      if (metricsRes.status === "fulfilled") setMetrics(metricsRes.value);
      if (dashRes.status === "fulfilled") setDashboard(dashRes.value);
      if (msgRes.status === "fulfilled") setMessageTrends(msgRes.value.trends || msgRes.value.data || []);
      if (respRes.status === "fulfilled") setResponseTrends(respRes.value.trends || respRes.value.data || []);
      if (healthRes.status === "fulfilled") setHealth(healthRes.value);
      setLastRefresh(new Date());
    } catch {
      setError("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  if (loading) return <><Header /><LoadingState message="Loading admin dashboard..." /></>;
  if (error) return <><Header /><ErrorState message={error} onRetry={loadAll} /></>;

  // Extract key numbers from whatever the backend returns
  const totalUsers = metrics?.total_users || dashboard?.total_users || 0;
  const activeToday = metrics?.active_users_today || dashboard?.active_today || 0;
  const totalConversations = metrics?.total_conversations || dashboard?.conversations || 0;
  const avgResponseTime = metrics?.avg_response_time_ms || dashboard?.avg_response_time || 0;
  const fallbackRate = metrics?.fallback_rate || dashboard?.fallback_rate || 0;
  const stateDistribution = metrics?.state_distribution || dashboard?.states || {};
  const intentDistribution = metrics?.intent_distribution || dashboard?.intents || {};
  const dauData = metrics?.daily_active_users || dashboard?.dau || [];

  return (
    <div className="min-h-screen bg-gray-50">
      <Header />

      <div className="px-4 md:px-8 py-6">
        {/* Title bar */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl md:text-3xl font-bold">Analytics Dashboard</h1>
            <p className="text-xs font-mono text-gray-400 mt-1">
              Last refreshed: {lastRefresh.toLocaleTimeString()}
            </p>
          </div>
          <button
            onClick={loadAll}
            className="bg-c-black text-white px-4 py-2 text-xs font-mono uppercase hover:bg-gray-800 transition-colors"
          >
            Refresh
          </button>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-8">
          <StatsCard label="Total Users" value={totalUsers.toLocaleString()} icon={"\uD83D\uDC65"} />
          <StatsCard label="Active Today" value={activeToday.toLocaleString()} color="#487A3A" icon={"\uD83D\uDFE2"} />
          <StatsCard label="Conversations" value={totalConversations.toLocaleString()} icon={"\uD83D\uDCAC"} />
          <StatsCard
            label="Avg Response"
            value={avgResponseTime > 0 ? `${(avgResponseTime / 1000).toFixed(1)}s` : "N/A"}
            icon={"\u23F1\uFE0F"}
          />
          <StatsCard
            label="Fallback Rate"
            value={fallbackRate > 0 ? `${(fallbackRate * 100).toFixed(1)}%` : "N/A"}
            color={fallbackRate > 0.15 ? "#D6453A" : "#487A3A"}
            icon={"\u26A0\uFE0F"}
          />
          <StatsCard
            label="Documents"
            value={health?.document_count?.toLocaleString() || "N/A"}
            icon={"\uD83D\uDCC4"}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* State Distribution */}
          <div className="bg-white border border-gray-200 p-5">
            <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wider mb-4">Users by State</h2>
            {Object.keys(stateDistribution).length > 0 ? (
              <div className="space-y-2 max-h-[400px] overflow-y-auto">
                {Object.entries(stateDistribution)
                  .sort(([, a]: any, [, b]: any) => b - a)
                  .map(([state, count]: [string, any]) => {
                    const maxCount = Math.max(...Object.values(stateDistribution).map(Number));
                    const percentage = maxCount > 0 ? (count / maxCount) * 100 : 0;
                    return (
                      <div key={state} className="flex items-center gap-3">
                        <span className="text-xs font-mono w-24 text-right text-gray-600 truncate">{state}</span>
                        <div className="flex-1 bg-gray-100 h-5 relative">
                          <div
                            className="absolute inset-y-0 left-0 bg-c-green transition-all"
                            style={{ width: `${percentage}%` }}
                          />
                          <span className="absolute right-2 top-0.5 text-[10px] font-mono text-gray-500">
                            {count}
                          </span>
                        </div>
                      </div>
                    );
                  })}
              </div>
            ) : (
              <p className="text-sm text-gray-400">No state data available yet</p>
            )}
          </div>

          {/* Intent Distribution */}
          <div className="bg-white border border-gray-200 p-5">
            <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wider mb-4">Query Intents</h2>
            {Object.keys(intentDistribution).length > 0 ? (
              <div className="space-y-2 max-h-[400px] overflow-y-auto">
                {Object.entries(intentDistribution)
                  .sort(([, a]: any, [, b]: any) => b - a)
                  .map(([intent, count]: [string, any]) => {
                    const maxCount = Math.max(...Object.values(intentDistribution).map(Number));
                    const percentage = maxCount > 0 ? (count / maxCount) * 100 : 0;
                    return (
                      <div key={intent} className="flex items-center gap-3">
                        <span className="text-xs font-mono w-32 text-right text-gray-600 truncate">{intent}</span>
                        <div className="flex-1 bg-gray-100 h-5 relative">
                          <div
                            className="absolute inset-y-0 left-0 bg-c-blue transition-all"
                            style={{ width: `${percentage}%` }}
                          />
                          <span className="absolute right-2 top-0.5 text-[10px] font-mono text-gray-500">
                            {count}
                          </span>
                        </div>
                      </div>
                    );
                  })}
              </div>
            ) : (
              <p className="text-sm text-gray-400">No intent data available yet</p>
            )}
          </div>
        </div>

        {/* DAU Chart (simple bar visualization) */}
        {dauData.length > 0 && (
          <div className="bg-white border border-gray-200 p-5 mb-8">
            <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wider mb-4">Daily Active Users (Last 30 Days)</h2>
            <div className="flex items-end gap-1 h-40">
              {dauData.slice(-30).map((d: any, i: number) => {
                const maxVal = Math.max(...dauData.map((x: any) => x.count || 0));
                const height = maxVal > 0 ? ((d.count || 0) / maxVal) * 100 : 0;
                return (
                  <div key={i} className="flex-1 flex flex-col items-center justify-end gap-1" title={`${d.date}: ${d.count}`}>
                    <div
                      className="w-full bg-c-green/80 hover:bg-c-green transition-colors rounded-t-sm min-h-[2px]"
                      style={{ height: `${height}%` }}
                    />
                  </div>
                );
              })}
            </div>
            <div className="flex justify-between mt-2 text-[9px] font-mono text-gray-400">
              <span>{dauData[Math.max(0, dauData.length - 30)]?.date || ""}</span>
              <span>{dauData[dauData.length - 1]?.date || ""}</span>
            </div>
          </div>
        )}

        {/* Message Trends */}
        {messageTrends.length > 0 && (
          <div className="bg-white border border-gray-200 p-5 mb-8">
            <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wider mb-4">Message Volume Trends</h2>
            <div className="flex items-end gap-1 h-32">
              {messageTrends.slice(-30).map((d: any, i: number) => {
                const maxVal = Math.max(...messageTrends.map((x: any) => x.count || x.messages || 0));
                const val = d.count || d.messages || 0;
                const height = maxVal > 0 ? (val / maxVal) * 100 : 0;
                return (
                  <div
                    key={i}
                    className="flex-1 bg-c-yellow/70 hover:bg-c-yellow transition-colors rounded-t-sm min-h-[2px]"
                    style={{ height: `${height}%` }}
                    title={`${d.date || d.period}: ${val}`}
                  />
                );
              })}
            </div>
          </div>
        )}

        {/* System Health */}
        <div className="bg-white border border-gray-200 p-5 mb-8">
          <h2 className="text-sm font-mono text-gray-400 uppercase tracking-wider mb-4">System Health</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center">
              <div className={`w-4 h-4 rounded-full mx-auto mb-2 ${health?.status === 'ok' ? 'bg-c-green' : 'bg-c-red'}`} />
              <span className="text-xs font-mono text-gray-500">API Status</span>
              <p className="font-bold text-sm">{health?.status === 'ok' ? 'Healthy' : 'Unknown'}</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold">{health?.document_count?.toLocaleString() || 'N/A'}</p>
              <span className="text-xs font-mono text-gray-500">RAG Documents</span>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold">{health?.politician_count?.toLocaleString() || 'N/A'}</p>
              <span className="text-xs font-mono text-gray-500">Politicians</span>
            </div>
            <div className="text-center">
              <p className="text-2xl font-bold">{health?.database_status || 'N/A'}</p>
              <span className="text-xs font-mono text-gray-500">Database</span>
            </div>
          </div>
        </div>

        {/* Quick links */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <a href="/issues" className="bg-white border border-gray-200 p-4 hover:border-c-green transition-colors text-center">
            <span className="text-2xl block mb-1">{"\uD83D\uDCCA"}</span>
            <span className="text-sm font-bold">Issues</span>
          </a>
          <a href="/chat" className="bg-white border border-gray-200 p-4 hover:border-c-green transition-colors text-center">
            <span className="text-2xl block mb-1">{"\uD83D\uDCAC"}</span>
            <span className="text-sm font-bold">Chat</span>
          </a>
          <a href="/explore" className="bg-white border border-gray-200 p-4 hover:border-c-green transition-colors text-center">
            <span className="text-2xl block mb-1">{"\uD83D\uDD0D"}</span>
            <span className="text-sm font-bold">Explore</span>
          </a>
          <a
            href="https://decide9ja.up.railway.app/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="bg-white border border-gray-200 p-4 hover:border-c-green transition-colors text-center"
          >
            <span className="text-2xl block mb-1">{"\uD83D\uDCDA"}</span>
            <span className="text-sm font-bold">API Docs</span>
          </a>
        </div>
      </div>
    </div>
  );
}
