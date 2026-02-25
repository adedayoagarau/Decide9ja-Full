/**
 * Formatting utilities for Decide9ja
 */

export function formatAmount(amount: number): string {
  if (amount >= 1_000_000_000_000) {
    return `\u20A6${(amount / 1_000_000_000_000).toFixed(1)}T`;
  } else if (amount >= 1_000_000_000) {
    return `\u20A6${(amount / 1_000_000_000).toFixed(1)}B`;
  } else if (amount >= 1_000_000) {
    return `\u20A6${(amount / 1_000_000).toFixed(1)}M`;
  }
  return `\u20A6${amount.toLocaleString()}`;
}

export function formatDate(date: Date = new Date()): string {
  return `${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}.${String(date.getFullYear()).slice(-2)}`;
}

export function truncate(text: string, maxLength: number): string {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

export function timeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (seconds < 60) return 'just now';
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
  return date.toLocaleDateString('en-NG', { month: 'short', day: 'numeric' });
}

export function severityColor(severity: string): string {
  switch (severity?.toUpperCase()) {
    case 'CRITICAL': case 'SEVERE': return '#D6453A';
    case 'HIGH': return '#164678';
    case 'MEDIUM': case 'MODERATE': return '#EBC346';
    case 'LOW': return '#D9D9CD';
    default: return '#9E7D45';
  }
}

export function domainIcon(domain: string): string {
  const icons: Record<string, string> = {
    power: '\u26A1',
    roads: '\uD83D\uDEE3\uFE0F',
    security: '\uD83D\uDEE1\uFE0F',
    water: '\uD83D\uDCA7',
    health: '\uD83C\uDFE5',
    education: '\uD83C\uDF93',
  };
  return icons[domain?.toLowerCase()] || '\uD83D\uDCCB';
}
