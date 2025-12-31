import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Issue } from "@/lib/api";

interface IssueCardProps {
    issue: Issue;
}

const severityColors = {
    low: "bg-green-500/10 text-green-400 border-green-500/20",
    moderate: "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
    severe: "bg-red-500/10 text-red-400 border-red-500/20",
};

const severityEmojis = {
    low: "🟢",
    moderate: "🟡",
    severe: "🔴",
};

const domainEmojis: Record<string, string> = {
    power: "🔌",
    roads: "🛣️",
    infrastructure: "🏗️",
    security: "🔒",
    water: "💧",
    health: "🏥",
    education: "📚",
    waste: "🗑️",
    flooding: "🌊",
};

export function IssueCard({ issue }: IssueCardProps) {
    const location = issue.location || issue.states?.join(", ") || "Nigeria";
    const updatedAt = issue.last_updated || "Recently";

    return (
        <Link href={`/issues/${issue.issue_id}`}>
            <Card className="group hover:shadow-lg hover:border-primary/30 transition-all cursor-pointer h-full bg-card border-border">
                <CardContent className="p-5">
                    {/* Header */}
                    <div className="flex items-start justify-between gap-2 mb-3">
                        <Badge
                            variant="outline"
                            className={severityColors[issue.severity]}
                        >
                            {severityEmojis[issue.severity]} {issue.severity.toUpperCase()}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                            {domainEmojis[issue.domain.toLowerCase()] || "📋"} {issue.domain}
                        </span>
                    </div>

                    {/* Title */}
                    <h3 className="font-semibold text-base text-foreground group-hover:text-primary transition-colors line-clamp-2 mb-3">
                        {issue.title}
                    </h3>

                    {/* Meta */}
                    <div className="space-y-1 text-sm text-muted-foreground">
                        <div className="flex items-center gap-1">
                            <span>📍</span> {location}
                        </div>
                        <div className="flex items-center gap-1">
                            <span>📅</span> Updated {updatedAt}
                        </div>
                        {issue.event_count && issue.event_count > 0 && (
                            <div className="flex items-center gap-1">
                                <span>📊</span> {issue.event_count} reports
                            </div>
                        )}
                    </div>

                    {/* View Link */}
                    <div className="mt-4 text-sm text-primary font-medium group-hover:underline">
                        View Issue →
                    </div>
                </CardContent>
            </Card>
        </Link>
    );
}
