"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Header from "@/components/Header";
import ChatWidget from "@/components/ChatWidget";
import LoadingState from "@/components/LoadingState";
import ErrorState from "@/components/ErrorState";
import { getIssueDetail } from "@/lib/api";
import type { IssueDetail } from "@/lib/api";
import { severityColor, domainIcon, timeAgo } from "@/lib/format";

export default function IssueDetailPage() {
  const params = useParams();
  const issueId = params.id as string;
  const [issue, setIssue] = useState<IssueDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!issueId) return;
    setLoading(true);
    getIssueDetail(issueId)
      .then((data) => setIssue(data))
      .catch(() => setError("Failed to load issue"))
      .finally(() => setLoading(false));
  }, [issueId]);

  if (loading) return <><Header /><LoadingState message="Loading issue details..." /></>;
  if (error || !issue) return <><Header /><ErrorState message={error || "Issue not found"} /></>;

  const color = severityColor(issue.severity);

  return (
    <div className="min-h-screen bg-c-beige">
      <Header />

      <div className="max-w-4xl mx-auto px-4 md:px-8 py-8">
        {/* Breadcrumb */}
        <div className="text-xs font-mono text-gray-400 mb-6">
          <a href="/issues" className="hover:text-c-black">Issues</a>
          <span className="mx-2">/</span>
          <span className="text-c-black">{issue.title}</span>
        </div>

        {/* Header */}
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <span className="text-lg">{domainIcon(issue.domain)}</span>
          <span className="text-xs font-mono uppercase text-gray-500">{issue.domain}</span>
          <span
            className="text-[10px] font-mono uppercase px-2 py-0.5 font-bold"
            style={{ backgroundColor: color, color: issue.severity === 'high' ? '#fff' : '#000' }}
          >
            {issue.severity}
          </span>
          <span className={`text-[10px] font-mono uppercase px-2 py-0.5 border ${
            issue.status === 'active' ? 'border-c-green text-c-green' : 'border-gray-400 text-gray-400'
          }`}>
            {issue.status}
          </span>
          {issue.verified && (
            <span className="text-[10px] font-mono text-c-green bg-c-green/10 px-2 py-0.5">VERIFIED</span>
          )}
        </div>

        <h1 className="text-2xl md:text-4xl font-bold leading-tight mb-4">{issue.title}</h1>
        <p className="text-base md:text-lg text-gray-600 leading-relaxed mb-6">{issue.summary}</p>

        {/* Meta */}
        <div className="flex flex-wrap gap-4 text-xs font-mono text-gray-400 mb-8 pb-8 border-b border-gray-300">
          {issue.states && issue.states.length > 0 && (
            <span>States: {issue.states.join(', ')}</span>
          )}
          <span>{issue.event_count} events</span>
          <span>{issue.source_count} sources</span>
          {issue.first_reported && <span>First: {new Date(issue.first_reported).toLocaleDateString('en-NG')}</span>}
          {issue.last_updated && <span>Updated: {timeAgo(issue.last_updated)}</span>}
        </div>

        {/* Share */}
        <div className="flex gap-2 mb-8">
          <button
            onClick={() => {
              const text = `${issue.title}\n\n${issue.summary}\n\nhttps://decide9ja.com/issues/${issueId}\n#Decide9ja`;
              window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}`, '_blank');
            }}
            className="bg-c-black text-white px-4 py-2 text-xs font-mono uppercase hover:bg-gray-800"
          >
            Share on X
          </button>
          <button
            onClick={() => {
              const text = `*${issue.title}*\n\n${issue.summary}\n\nhttps://decide9ja.com/issues/${issueId}\n_Source: Decide9ja_`;
              window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank');
            }}
            className="bg-[#25D366] text-white px-4 py-2 text-xs font-mono uppercase hover:brightness-90"
          >
            WhatsApp
          </button>
          <button
            onClick={() => navigator.clipboard.writeText(`https://decide9ja.com/issues/${issueId}`)}
            className="bg-white border border-gray-300 px-4 py-2 text-xs font-mono uppercase hover:border-gray-500"
          >
            Copy Link
          </button>
        </div>

        {/* Timeline */}
        {issue.events && issue.events.length > 0 && (
          <div className="mb-8">
            <h2 className="text-lg font-bold mb-4">Timeline</h2>
            <div className="space-y-4">
              {issue.events
                .sort((a, b) => new Date(b.event_date).getTime() - new Date(a.event_date).getTime())
                .map((event) => (
                  <div key={event.event_id} className="bg-white border border-gray-200 p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[10px] font-mono text-gray-400 uppercase">{event.event_type}</span>
                      <span className="text-[10px] font-mono text-gray-400">
                        {new Date(event.event_date).toLocaleDateString('en-NG', { year: 'numeric', month: 'short', day: 'numeric' })}
                      </span>
                    </div>
                    <h3 className="font-bold text-sm mb-1">{event.title}</h3>
                    <p className="text-sm text-gray-600">{event.description}</p>
                    {event.source_name && (
                      <div className="mt-2">
                        {event.source_url ? (
                          <a href={event.source_url} target="_blank" rel="noopener noreferrer" className="text-[10px] font-mono text-c-blue hover:underline">
                            Source: {event.source_name}
                          </a>
                        ) : (
                          <span className="text-[10px] font-mono text-gray-400">Source: {event.source_name}</span>
                        )}
                      </div>
                    )}
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Related Politicians */}
        {issue.politicians && issue.politicians.length > 0 && (
          <div className="mb-8">
            <h2 className="text-lg font-bold mb-4">Related Politicians</h2>
            <div className="flex flex-wrap gap-2">
              {issue.politicians.map((pol: any, idx: number) => (
                <span key={idx} className="bg-white border border-gray-200 px-3 py-2 text-sm">
                  {pol.name || pol.politician_slug} {pol.role && <span className="text-gray-400 text-xs">({pol.role})</span>}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <ChatWidget />
    </div>
  );
}
