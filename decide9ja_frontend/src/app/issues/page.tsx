"use client";

import { useState, useEffect, useCallback } from "react";
import Header from "@/components/Header";
import IssueCard from "@/components/IssueCard";
import ChatWidget from "@/components/ChatWidget";
import LoadingState from "@/components/LoadingState";
import ErrorState from "@/components/ErrorState";
import { getIssues, getIssueDomains } from "@/lib/api";
import type { Issue } from "@/lib/api";
import { ISSUE_DOMAINS } from "@/lib/constants";

export default function IssuesPage() {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [domainCounts, setDomainCounts] = useState<Record<string, number>>({});

  // Filters
  const [domain, setDomain] = useState<string>("");
  const [severity, setSeverity] = useState<string>("");
  const [status, setStatus] = useState<string>("active");
  const [offset, setOffset] = useState(0);
  const LIMIT = 20;

  // Read initial domain from URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const d = params.get("domain");
    if (d) setDomain(d);
  }, []);

  const loadIssues = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getIssues({
        domain: domain || undefined,
        severity: severity || undefined,
        status: status || undefined,
        limit: LIMIT,
        offset,
      });
      setIssues(data.issues || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError("Failed to load issues");
    } finally {
      setLoading(false);
    }
  }, [domain, severity, status, offset]);

  useEffect(() => {
    loadIssues();
  }, [loadIssues]);

  useEffect(() => {
    getIssueDomains()
      .then((data) => {
        const counts: Record<string, number> = {};
        (data.domains || []).forEach((d: any) => { counts[d.domain] = d.count; });
        setDomainCounts(counts);
      })
      .catch(() => {});
  }, []);

  const resetFilters = () => {
    setDomain("");
    setSeverity("");
    setStatus("active");
    setOffset(0);
  };

  return (
    <div className="min-h-screen bg-c-beige">
      <Header />

      <div className="px-4 md:px-8 py-6">
        <h1 className="text-2xl md:text-3xl font-bold mb-1">Political Issues</h1>
        <p className="text-sm text-gray-500 font-mono mb-6">
          {total > 0 ? `${total} issues tracked` : "Loading..."}
        </p>

        {/* Filters */}
        <div className="flex flex-wrap gap-2 mb-6">
          {/* Domain pills */}
          <button
            onClick={() => { setDomain(""); setOffset(0); }}
            className={`text-xs font-mono uppercase px-3 py-1.5 border transition-colors ${
              !domain ? "bg-c-black text-white border-c-black" : "bg-white border-gray-300 hover:border-gray-500"
            }`}
          >
            All Domains
          </button>
          {ISSUE_DOMAINS.map((d) => (
            <button
              key={d}
              onClick={() => { setDomain(d); setOffset(0); }}
              className={`text-xs font-mono uppercase px-3 py-1.5 border transition-colors ${
                domain === d ? "bg-c-black text-white border-c-black" : "bg-white border-gray-300 hover:border-gray-500"
              }`}
            >
              {d} {domainCounts[d] ? `(${domainCounts[d]})` : ""}
            </button>
          ))}

          <span className="w-px h-6 bg-gray-300 self-center mx-1" />

          {/* Severity filter */}
          <select
            value={severity}
            onChange={(e) => { setSeverity(e.target.value); setOffset(0); }}
            className="text-xs font-mono uppercase px-3 py-1.5 border border-gray-300 bg-white outline-none"
          >
            <option value="">All Severity</option>
            <option value="severe">Severe</option>
            <option value="moderate">Moderate</option>
            <option value="low">Low</option>
          </select>

          {/* Status filter */}
          <select
            value={status}
            onChange={(e) => { setStatus(e.target.value); setOffset(0); }}
            className="text-xs font-mono uppercase px-3 py-1.5 border border-gray-300 bg-white outline-none"
          >
            <option value="">All Status</option>
            <option value="active">Active</option>
            <option value="resolved">Resolved</option>
            <option value="archived">Archived</option>
          </select>

          {(domain || severity || status !== "active") && (
            <button
              onClick={resetFilters}
              className="text-xs font-mono text-c-red hover:underline ml-2"
            >
              Clear filters
            </button>
          )}
        </div>

        {/* Results */}
        {loading ? (
          <LoadingState message="Fetching issues..." />
        ) : error ? (
          <ErrorState message={error} onRetry={loadIssues} />
        ) : issues.length === 0 ? (
          <div className="text-center py-16">
            <p className="text-gray-500">No issues match your filters</p>
            <button onClick={resetFilters} className="text-sm font-mono text-c-blue hover:underline mt-2">
              Reset filters
            </button>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {issues.map((issue) => (
                <IssueCard
                  key={issue.issue_id}
                  issue={issue}
                  onClick={() => window.location.href = `/issues/${issue.issue_id}`}
                />
              ))}
            </div>

            {/* Pagination */}
            {total > LIMIT && (
              <div className="flex items-center justify-center gap-3 mt-8">
                <button
                  onClick={() => setOffset(Math.max(0, offset - LIMIT))}
                  disabled={offset === 0}
                  className="text-xs font-mono bg-c-black text-white px-4 py-2 disabled:opacity-30"
                >
                  &larr; Previous
                </button>
                <span className="text-xs font-mono text-gray-500">
                  {offset + 1}–{Math.min(offset + LIMIT, total)} of {total}
                </span>
                <button
                  onClick={() => setOffset(offset + LIMIT)}
                  disabled={offset + LIMIT >= total}
                  className="text-xs font-mono bg-c-black text-white px-4 py-2 disabled:opacity-30"
                >
                  Next &rarr;
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <ChatWidget />
    </div>
  );
}
