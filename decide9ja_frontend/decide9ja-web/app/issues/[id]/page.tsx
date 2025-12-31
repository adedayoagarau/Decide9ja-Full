"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Issue, api, getPartyColor } from "@/lib/api";
import Link from "next/link";

const severityColors = {
    low: "bg-green-100 text-green-800 border-green-200",
    moderate: "bg-yellow-100 text-yellow-800 border-yellow-200",
    severe: "bg-red-100 text-red-800 border-red-200",
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
    economy: "💰",
    governance: "🏛️",
    environment: "🌳",
    transport: "🚆",
};

export default function IssueDetailPage() {
    const params = useParams();
    const issueId = params.id as string;
    const [issue, setIssue] = useState<Issue | null>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        api.issues
            .get(issueId)
            .then(setIssue)
            .catch(() => setIssue(null))
            .finally(() => setLoading(false));
    }, [issueId]);

    if (loading) {
        return (
            <div className="container py-12 text-center text-muted-foreground">
                Loading issue...
            </div>
        );
    }

    if (!issue) {
        return (
            <div className="container py-12 text-center">
                <h1 className="text-2xl font-bold mb-4">Issue not found</h1>
                <Link href="/issues">
                    <Button>← Back to Issues</Button>
                </Link>
            </div>
        );
    }

    return (
        <div className="container py-8 md:py-12">
            {/* Back Link */}
            <Link
                href="/issues"
                className="text-muted-foreground hover:text-primary text-sm mb-6 inline-block"
            >
                ← Back to Issues
            </Link>

            {/* Issue Header */}
            <Card className="mb-8">
                <CardContent className="p-6 md:p-8">
                    <div className="flex flex-wrap items-start gap-4 mb-4">
                        <Badge
                            variant="outline"
                            className={severityColors[issue.severity as keyof typeof severityColors] || severityColors.moderate}
                        >
                            {severityEmojis[issue.severity as keyof typeof severityEmojis] || "🟡"} {(issue.severity || "moderate").toUpperCase()}
                        </Badge>
                        <Badge variant="secondary">
                            {domainEmojis[issue.domain?.toLowerCase()] || "📋"} {issue.domain}
                        </Badge>
                        {issue.verified && (
                            <Badge className="bg-green-600 text-white">✓ Verified</Badge>
                        )}
                    </div>

                    <h1 className="text-2xl md:text-3xl font-bold mb-4">{issue.title}</h1>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-muted-foreground">
                        <div>
                            <span className="font-medium">📍 Location:</span> {issue.location || "Nationwide"}
                        </div>
                        <div>
                            <span className="font-medium">📅 First Reported:</span>{" "}
                            {issue.first_reported ? new Date(issue.first_reported).toLocaleDateString() : "Unknown"}
                        </div>
                        <div>
                            <span className="font-medium">🔄 Last Updated:</span>{" "}
                            {issue.last_updated ? new Date(issue.last_updated).toLocaleDateString() : "Unknown"}
                        </div>
                    </div>

                    {issue.summary && (
                        <p className="mt-6 text-muted-foreground">{issue.summary}</p>
                    )}
                </CardContent>
            </Card>

            {/* Timeline */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <div className="lg:col-span-2">
                    <h2 className="text-xl font-semibold mb-4">📰 Event Timeline</h2>

                    {issue.events && issue.events.length > 0 ? (
                        <div className="space-y-4">
                            {issue.events.map((event, i) => (
                                <Card key={event.event_id || i}>
                                    <CardContent className="p-5">
                                        <div className="flex items-start gap-4">
                                            <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                                                📰
                                            </div>
                                            <div className="flex-1">
                                                <div className="text-sm text-muted-foreground mb-1">
                                                    {event.event_date ? new Date(event.event_date).toLocaleDateString() : ""}
                                                    {event.source_name && ` • ${event.source_name}`}
                                                </div>
                                                <h3 className="font-semibold">{event.title}</h3>
                                                {event.description && (
                                                    <p className="text-sm text-muted-foreground mt-2">{event.description}</p>
                                                )}
                                                {event.source_url && (
                                                    <a
                                                        href={event.source_url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="text-sm text-primary hover:underline mt-2 inline-block"
                                                    >
                                                        Read source →
                                                    </a>
                                                )}
                                            </div>
                                        </div>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    ) : (
                        <Card>
                            <CardContent className="p-6 text-center text-muted-foreground">
                                No events recorded yet.
                            </CardContent>
                        </Card>
                    )}
                </div>

                {/* Politicians Sidebar */}
                <div>
                    <h2 className="text-xl font-semibold mb-4">👤 Linked Politicians</h2>

                    {issue.politicians && issue.politicians.length > 0 ? (
                        <div className="space-y-3">
                            {issue.politicians.map((pol, i) => (
                                <Card key={pol.slug || i}>
                                    <CardContent className="p-4">
                                        <Link href={`/politicians/${pol.slug}`}>
                                            <div className="flex items-center gap-3">
                                                <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                                                    👤
                                                </div>
                                                <div className="flex-1 min-w-0">
                                                    <div className="font-medium truncate hover:text-primary">
                                                        {pol.name}
                                                    </div>
                                                    <div className="text-sm text-muted-foreground flex items-center gap-2">
                                                        <Badge
                                                            style={{ backgroundColor: getPartyColor(pol.party) }}
                                                            className="text-white text-xs"
                                                        >
                                                            {pol.party}
                                                        </Badge>
                                                        <span className="capitalize">{pol.role}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </Link>
                                    </CardContent>
                                </Card>
                            ))}
                        </div>
                    ) : (
                        <Card>
                            <CardContent className="p-4 text-center text-muted-foreground text-sm">
                                No politicians linked yet.
                            </CardContent>
                        </Card>
                    )}

                    {/* Report CTA */}
                    <Card className="mt-6 bg-muted/50">
                        <CardContent className="p-4 text-center">
                            <p className="text-sm text-muted-foreground mb-3">
                                Have more information about this issue?
                            </p>
                            <a href={`https://wa.me/2348160179151?text=I have info about: ${encodeURIComponent(issue.title)}`}>
                                <Button size="sm">📝 Report via WhatsApp</Button>
                            </a>
                        </CardContent>
                    </Card>
                </div>
            </div>
        </div>
    );
}
