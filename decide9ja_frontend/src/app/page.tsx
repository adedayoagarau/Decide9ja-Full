"use client";

import { useState, useEffect } from "react";
import Header from "@/components/Header";
import IssueCard from "@/components/IssueCard";
import StatsCard from "@/components/StatsCard";
import ChatWidget from "@/components/ChatWidget";
import LoadingState from "@/components/LoadingState";
import { getTrendingIssues, getIssueDomains, getDetailedHealth } from "@/lib/api";
import type { Issue } from "@/lib/api";
import { domainIcon } from "@/lib/format";

export default function Home() {
  const [trending, setTrending] = useState<Issue[]>([]);
  const [domains, setDomains] = useState<{ domain: string; count: number }[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      try {
        const [trendRes, domainRes, healthRes] = await Promise.allSettled([
          getTrendingIssues(12),
          getIssueDomains(),
          getDetailedHealth(),
        ]);

        if (trendRes.status === "fulfilled") setTrending(trendRes.value.issues || []);
        if (domainRes.status === "fulfilled") setDomains(domainRes.value.domains || []);
        if (healthRes.status === "fulfilled") setHealth(healthRes.value);
      } catch (err) {
        setError("Failed to connect to backend");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="min-h-screen bg-c-beige">
      <Header />

      {/* Hero */}
      <section className="bg-c-black text-white px-4 md:px-8 py-12 md:py-20 border-b border-c-border">
        <div className="max-w-5xl">
          <h1 className="text-3xl md:text-5xl lg:text-6xl font-bold leading-tight mb-4">
            Know your government.<br />
            <span className="text-c-green">Hold them accountable.</span>
          </h1>
          <p className="text-gray-400 text-base md:text-lg max-w-2xl mb-8 leading-relaxed">
            AI-powered intelligence tracking Nigerian politics, issues, bills, and budgets.
            Real-time analysis from 80+ data endpoints.
          </p>
          <div className="flex flex-wrap gap-3">
            <a href="/issues" className="bg-c-green text-white px-6 py-3 font-mono text-sm uppercase hover:brightness-110 transition-colors">
              Browse Issues
            </a>
            <a href="/chat" className="bg-white text-c-black px-6 py-3 font-mono text-sm uppercase hover:bg-gray-100 transition-colors">
              Ask Tade AI
            </a>
            <a href="/admin" className="border border-gray-600 text-gray-300 px-6 py-3 font-mono text-sm uppercase hover:border-white hover:text-white transition-colors">
              Analytics Dashboard
            </a>
          </div>
        </div>
      </section>

      {/* Stats bar */}
      <section className="px-4 md:px-8 py-6 border-b border-gray-300">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <StatsCard
            label="Tracked Issues"
            value={trending.length > 0 ? `${trending.length}+` : "..."}
            icon={"\uD83D\uDCCA"}
          />
          <StatsCard
            label="Issue Domains"
            value={domains.length || "..."}
            icon={"\uD83C\uDFAF"}
          />
          <StatsCard
            label="Documents Indexed"
            value={health?.document_count?.toLocaleString() || "..."}
            icon={"\uD83D\uDCC4"}
          />
          <StatsCard
            label="Politicians Tracked"
            value={health?.politician_count?.toLocaleString() || "..."}
            icon={"\uD83C\uDFDB\uFE0F"}
          />
        </div>
      </section>

      {/* Domain quick access */}
      {domains.length > 0 && (
        <section className="px-4 md:px-8 py-6 border-b border-gray-300">
          <h2 className="text-xs font-mono text-gray-400 uppercase tracking-wider mb-4">Issue Domains</h2>
          <div className="flex flex-wrap gap-2">
            {domains.map((d) => (
              <a
                key={d.domain}
                href={`/issues?domain=${d.domain}`}
                className="flex items-center gap-2 bg-white border border-gray-200 px-4 py-2.5 hover:border-c-green hover:bg-c-green/5 transition-colors"
              >
                <span className="text-lg">{domainIcon(d.domain)}</span>
                <span className="text-sm font-bold uppercase">{d.domain}</span>
                <span className="text-[10px] font-mono text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                  {d.count}
                </span>
              </a>
            ))}
          </div>
        </section>
      )}

      {/* Trending Issues */}
      <section className="px-4 md:px-8 py-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg md:text-xl font-bold">Trending Issues</h2>
          <a href="/issues" className="text-xs font-mono text-c-blue hover:underline uppercase">
            View All &rarr;
          </a>
        </div>

        {loading ? (
          <LoadingState message="Loading latest issues from backend..." />
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-gray-500 mb-2">{error}</p>
            <p className="text-xs font-mono text-gray-400">Make sure the backend is running at decide9ja.up.railway.app</p>
          </div>
        ) : trending.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500">No trending issues found</p>
            <p className="text-xs font-mono text-gray-400 mt-1">Issues will appear here as the system collects data</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {trending.map((issue) => (
              <IssueCard
                key={issue.issue_id}
                issue={issue}
                onClick={() => window.location.href = `/issues/${issue.issue_id}`}
              />
            ))}
          </div>
        )}
      </section>

      {/* CTA */}
      <section className="px-4 md:px-8 py-12 bg-c-black text-white">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-2xl md:text-3xl font-bold mb-4">Chat with Tade on WhatsApp</h2>
          <p className="text-gray-400 mb-6">Get political updates, ask questions, report issues - all from your WhatsApp.</p>
          <a
            href="https://wa.me/your_number"
            className="inline-block bg-[#25D366] text-white px-8 py-3 font-mono text-sm uppercase hover:brightness-110 transition-colors"
          >
            Start WhatsApp Chat
          </a>
        </div>
      </section>

      <ChatWidget />
    </div>
  );
}
