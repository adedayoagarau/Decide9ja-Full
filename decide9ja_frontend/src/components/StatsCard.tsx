"use client";

interface StatsCardProps {
  label: string;
  value: string | number;
  change?: string;
  color?: string;
  icon?: string;
}

export default function StatsCard({ label, value, change, color = '#050505', icon }: StatsCardProps) {
  return (
    <div className="bg-white border border-gray-200 p-4 md:p-5 hover:border-gray-400 transition-colors">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-mono text-gray-400 uppercase tracking-wider">{label}</span>
        {icon && <span className="text-lg">{icon}</span>}
      </div>
      <div className="text-2xl md:text-3xl font-bold" style={{ color }}>
        {value}
      </div>
      {change && (
        <span className={`text-xs font-mono mt-1 inline-block ${
          change.startsWith('+') ? 'text-c-green' : change.startsWith('-') ? 'text-c-red' : 'text-gray-400'
        }`}>
          {change}
        </span>
      )}
    </div>
  );
}
