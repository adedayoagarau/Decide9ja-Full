"use client";

import { severityColor, domainIcon, timeAgo, truncate } from "@/lib/format";
import type { Issue } from "@/lib/api";

export default function IssueCard({ issue, onClick }: { issue: Issue; onClick?: () => void }) {
  const color = severityColor(issue.severity);

  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-white border border-gray-200 hover:border-gray-400 transition-all p-4 md:p-5 group"
    >
      {/* Top row: domain + severity */}
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs font-mono text-gray-500 uppercase flex items-center gap-1.5">
          <span>{domainIcon(issue.domain)}</span>
          {issue.domain}
        </span>
        <span
          className="text-[10px] font-mono uppercase px-2 py-0.5 font-bold"
          style={{ backgroundColor: color, color: issue.severity === 'HIGH' ? '#fff' : '#000' }}
        >
          {issue.severity}
        </span>
      </div>

      {/* Title */}
      <h3 className="text-base md:text-lg font-bold leading-tight mb-2 group-hover:text-c-blue transition-colors">
        {truncate(issue.title, 80)}
      </h3>

      {/* Summary */}
      <p className="text-sm text-gray-600 leading-relaxed mb-3">
        {truncate(issue.summary, 120)}
      </p>

      {/* Bottom meta */}
      <div className="flex items-center justify-between text-[10px] font-mono text-gray-400">
        <div className="flex items-center gap-3">
          {issue.states && issue.states.length > 0 && (
            <span>{issue.states.slice(0, 2).join(', ')}{issue.states.length > 2 ? ` +${issue.states.length - 2}` : ''}</span>
          )}
          <span>{issue.event_count} events</span>
          <span>{issue.source_count} sources</span>
        </div>
        <div className="flex items-center gap-2">
          {issue.verified && (
            <span className="text-c-green font-bold">VERIFIED</span>
          )}
          {issue.last_updated && (
            <span>{timeAgo(issue.last_updated)}</span>
          )}
        </div>
      </div>
    </button>
  );
}
