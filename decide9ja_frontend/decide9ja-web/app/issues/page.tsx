"use client";

import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { IssueCard } from "@/components/issues/issue-card";
import { Issue, api, NIGERIAN_STATES } from "@/lib/api";

// Demo issues
const demoIssues: Issue[] = [
    { issue_id: "1", title: "National Grid Collapse #7 (2024)", domain: "Power", severity: "severe", location: "Nationwide", states: ["Federal"], last_updated: "2 hours ago", event_count: 12, status: "active" },
    { issue_id: "2", title: "Lagos-Ibadan Expressway Reconstruction Delays", domain: "Infrastructure", severity: "moderate", location: "Lagos, Ogun", states: ["Lagos", "Ogun"], last_updated: "1 day ago", event_count: 24, status: "active" },
    { issue_id: "3", title: "Kaduna-Abuja Rail Safety Concerns", domain: "Security", severity: "moderate", location: "Kaduna, FCT", states: ["Kaduna", "FCT"], last_updated: "3 days ago", event_count: 5, status: "active" },
    { issue_id: "4", title: "Flooding in Lekki Phase 1", domain: "Flooding", severity: "moderate", location: "Lagos", states: ["Lagos"], last_updated: "5 days ago", event_count: 8, status: "active" },
    { issue_id: "5", title: "Water Scarcity in Kubwa", domain: "Water", severity: "moderate", location: "FCT", states: ["FCT"], last_updated: "1 week ago", event_count: 3, status: "active" },
    { issue_id: "6", title: "Broken Street Lights in Agege", domain: "Infrastructure", severity: "low", location: "Lagos", states: ["Lagos"], last_updated: "2 weeks ago", event_count: 2, status: "active" },
];

const domains = ["Power", "Infrastructure", "Security", "Water", "Health", "Education", "Flooding", "Waste"];

export default function IssuesPage() {
    const [issues, setIssues] = useState<Issue[]>(demoIssues);
    const [filtered, setFiltered] = useState<Issue[]>(demoIssues);
    const [search, setSearch] = useState("");
    const [domainFilter, setDomainFilter] = useState("all");
    const [stateFilter, setStateFilter] = useState("all");
    const [severityFilter, setSeverityFilter] = useState("all");

    // Load from API
    useEffect(() => {
        api.issues
            .list()
            .then((data) => {
                if (data && data.length > 0) {
                    setIssues(data);
                    setFiltered(data);
                }
            })
            .catch(() => { });
    }, []);

    // Filter issues
    useEffect(() => {
        let result = issues;

        if (search) {
            const q = search.toLowerCase();
            result = result.filter((i) => i.title.toLowerCase().includes(q));
        }

        if (domainFilter !== "all") {
            result = result.filter((i) => i.domain.toLowerCase() === domainFilter.toLowerCase());
        }

        if (stateFilter !== "all") {
            result = result.filter((i) => i.states?.includes(stateFilter) || i.location?.includes(stateFilter));
        }

        if (severityFilter !== "all") {
            result = result.filter((i) => i.severity === severityFilter);
        }

        setFiltered(result);
    }, [search, domainFilter, stateFilter, severityFilter, issues]);

    // Stats
    const byDomain = domains.map((d) => ({
        domain: d,
        count: issues.filter((i) => i.domain.toLowerCase() === d.toLowerCase()).length,
    })).filter((d) => d.count > 0);

    return (
        <div className="container py-8 md:py-12">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl font-bold mb-2">Issues Tracker</h1>
                <p className="text-muted-foreground">
                    Tracking {issues.length} active issues across Nigeria
                </p>
            </div>

            {/* Domain Stats */}
            <div className="flex flex-wrap gap-3 mb-8">
                {byDomain.map((d) => (
                    <button
                        key={d.domain}
                        onClick={() => setDomainFilter(domainFilter === d.domain ? "all" : d.domain)}
                        className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${domainFilter === d.domain
                            ? "bg-primary text-primary-foreground"
                            : "bg-muted hover:bg-muted/80"
                            }`}
                    >
                        {d.domain} ({d.count})
                    </button>
                ))}
            </div>

            {/* Filters */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
                <Input
                    placeholder="🔍 Search issues..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                />

                <Select value={domainFilter} onValueChange={setDomainFilter}>
                    <SelectTrigger>
                        <SelectValue placeholder="Domain" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Domains</SelectItem>
                        {domains.map((d) => (
                            <SelectItem key={d} value={d.toLowerCase()}>
                                {d}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>

                <Select value={stateFilter} onValueChange={setStateFilter}>
                    <SelectTrigger>
                        <SelectValue placeholder="State" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All States</SelectItem>
                        {NIGERIAN_STATES.map((s) => (
                            <SelectItem key={s} value={s}>
                                {s}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>

                <Select value={severityFilter} onValueChange={setSeverityFilter}>
                    <SelectTrigger>
                        <SelectValue placeholder="Severity" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Severities</SelectItem>
                        <SelectItem value="severe">🔴 Severe</SelectItem>
                        <SelectItem value="moderate">🟡 Moderate</SelectItem>
                        <SelectItem value="low">🟢 Low</SelectItem>
                    </SelectContent>
                </Select>
            </div>

            {/* Results */}
            <div className="mb-4 text-muted-foreground">
                Showing {filtered.length} of {issues.length} issues
            </div>

            {/* Issue Grid */}
            {filtered.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {filtered.map((issue) => (
                        <IssueCard key={issue.issue_id} issue={issue} />
                    ))}
                </div>
            ) : (
                <div className="text-center py-12 text-muted-foreground">
                    No issues found matching your filters.
                </div>
            )}

            {/* Report CTA */}
            <div className="mt-12 text-center">
                <p className="text-muted-foreground mb-4">
                    See something that needs tracking? Report it.
                </p>
                <a href="https://wa.me/2348160179151?text=I want to report an issue">
                    <button className="bg-primary text-primary-foreground px-6 py-3 rounded-lg font-medium hover:bg-primary/90 transition-colors">
                        📝 Report Issue via WhatsApp
                    </button>
                </a>
            </div>
        </div>
    );
}
