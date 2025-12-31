"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Politician, api, getPartyColor } from "@/lib/api";
import Link from "next/link";

// Demo politician data
const demoPoliticians: Record<string, Politician & { bio: string; promises: any[] }> = {
    sanwoolu: {
        id: "sanwoolu",
        name: "Babajide Olusola Sanwo-Olu",
        position: "Governor of Lagos State",
        party: "APC",
        state: "Lagos",
        promiseScore: 31,
        term_start: "2019-05-29",
        bio: `Babajide Olusola Sanwo-Olu (born June 25, 1965) is a Nigerian politician serving as the Governor of Lagos State since May 2019. He is currently serving his second term.

Before becoming governor, he served as Commissioner for Commerce and Industry, Commissioner for Establishments, Training and Pensions, and Managing Director of First Atlantic Bank.

**Education:**
• University of Lagos (B.Sc. Surveying)
• London Business School (MBA)
• Harvard Kennedy School (Public Administration)

**Previous Positions:**
• MD/CEO, First Atlantic Bank
• Commissioner, Lagos Ministry of Commerce
• Commissioner, Establishments & Training`,
        promises: [
            { status: "kept", title: "Lagos Rail Mass Transit (Blue Line)", year: 2019, delivered: 2023, description: "13km rail line from Marina to Mile 2. Commercial operations began September 2023." },
            { status: "kept", title: "Oshodi Transport Interchange", year: 2019, delivered: 2019, description: "Multi-modal transport hub at Oshodi serving buses, BRT." },
            { status: "in_progress", title: "Fourth Mainland Bridge", year: 2019, description: "37km bridge from Lekki to Ikorodu. PPP model announced." },
            { status: "broken", title: "End Lagos Traffic in First Term", year: 2019, description: "Traffic remains a major issue despite some improvements." },
        ],
    },
    tinubu: {
        id: "tinubu",
        name: "Bola Ahmed Tinubu",
        position: "President of Nigeria",
        party: "APC",
        state: "Federal",
        promiseScore: 23,
        term_start: "2023-05-29",
        bio: `Bola Ahmed Tinubu (born March 29, 1952) is a Nigerian politician serving as the 16th President of Nigeria since May 29, 2023.

He previously served as the Governor of Lagos State from 1999 to 2007 and is considered a national leader of the All Progressives Congress (APC).

**Education:**
• Chicago State University (B.Sc. Accounting)
• Various professional certifications

**Previous Positions:**
• Governor of Lagos State (1999-2007)
• Senator for Lagos West (1992-1993)`,
        promises: [
            { status: "kept", title: "Fuel Subsidy Removal", year: 2023, delivered: 2023, description: "Removed fuel subsidies in first speech as president." },
            { status: "in_progress", title: "Economic Reforms", year: 2023, description: "Various economic policies being implemented." },
            { status: "in_progress", title: "Security Improvements", year: 2023, description: "Ongoing military operations in affected regions." },
        ],
    },
};

export default function PoliticianProfilePage() {
    const params = useParams();
    const id = params.id as string;
    const [politician, setPolitician] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        api.politicians
            .get(id)
            .then(setPolitician)
            .catch(() => {
                // Use demo data
                setPolitician(demoPoliticians[id] || demoPoliticians.sanwoolu);
            })
            .finally(() => setLoading(false));
    }, [id]);

    if (loading) {
        return (
            <div className="container py-12 text-center text-muted-foreground">
                Loading...
            </div>
        );
    }

    if (!politician) {
        return (
            <div className="container py-12 text-center">
                <h1 className="text-2xl font-bold mb-4">Politician not found</h1>
                <Link href="/politicians">
                    <Button>← Back to Directory</Button>
                </Link>
            </div>
        );
    }

    const promises = politician.promises || [];
    const kept = promises.filter((p: any) => p.status === "kept").length;
    const inProgress = promises.filter((p: any) => p.status === "in_progress").length;
    const broken = promises.filter((p: any) => p.status === "broken").length;

    return (
        <div className="container py-8 md:py-12">
            {/* Back Link */}
            <Link
                href="/politicians"
                className="text-muted-foreground hover:text-primary text-sm mb-6 inline-block"
            >
                ← Back to Politicians
            </Link>

            {/* Profile Header */}
            <Card className="mb-8">
                <CardContent className="p-6 md:p-8">
                    <div className="flex flex-col md:flex-row gap-6">
                        {/* Avatar */}
                        <div className="w-32 h-32 rounded-full bg-muted flex items-center justify-center text-5xl shrink-0 mx-auto md:mx-0">
                            👤
                        </div>

                        {/* Info */}
                        <div className="flex-1 text-center md:text-left">
                            <h1 className="text-3xl font-bold mb-2">{politician.name}</h1>
                            <p className="text-xl text-muted-foreground mb-3">
                                {politician.position}
                            </p>
                            <Badge
                                style={{ backgroundColor: getPartyColor(politician.party) }}
                                className="text-white"
                            >
                                {politician.party}
                            </Badge>
                            <div className="mt-4 text-sm text-muted-foreground space-y-1">
                                <div>📅 In office since: {politician.term_start || "N/A"}</div>
                                <div>📍 Represents: {politician.state}</div>
                            </div>

                            {/* WhatsApp CTA */}
                            <a
                                href={`https://wa.me/2348160179151?text=Tell me about ${politician.name}`}
                                className="inline-block mt-4"
                            >
                                <Button>💬 Ask about this politician</Button>
                            </a>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Tabs */}
            <Tabs defaultValue="overview" className="space-y-6">
                <TabsList>
                    <TabsTrigger value="overview">Overview</TabsTrigger>
                    <TabsTrigger value="promises">Promises</TabsTrigger>
                    <TabsTrigger value="issues">Related Issues</TabsTrigger>
                </TabsList>

                {/* Overview Tab */}
                <TabsContent value="overview" className="space-y-6">
                    {/* Quick Stats */}
                    {politician.promiseScore !== undefined && (
                        <Card>
                            <CardContent className="p-6">
                                <h2 className="font-semibold mb-4">Quick Stats</h2>
                                <div className="grid grid-cols-3 gap-4 text-center">
                                    <div>
                                        <div className="text-3xl font-bold text-primary">
                                            {politician.promiseScore}%
                                        </div>
                                        <div className="text-sm text-muted-foreground">
                                            Promise Score
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-3xl font-bold">{kept}</div>
                                        <div className="text-sm text-muted-foreground">
                                            Promises Kept
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-3xl font-bold">{inProgress}</div>
                                        <div className="text-sm text-muted-foreground">
                                            In Progress
                                        </div>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>
                    )}

                    {/* Biography */}
                    <Card>
                        <CardContent className="p-6">
                            <h2 className="font-semibold mb-4">Biography</h2>
                            <div className="prose prose-sm max-w-none text-muted-foreground whitespace-pre-line">
                                {politician.bio || "No biography available."}
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Promises Tab */}
                <TabsContent value="promises" className="space-y-6">
                    {/* Promise Summary */}
                    <Card>
                        <CardContent className="p-6">
                            <h2 className="font-semibold mb-4">Promise Tracker</h2>
                            {politician.promiseScore !== undefined && (
                                <>
                                    <div className="mb-4">
                                        <div className="flex justify-between text-sm mb-1">
                                            <span>Promise Score</span>
                                            <span className="font-medium">{politician.promiseScore}%</span>
                                        </div>
                                        <div className="h-3 bg-muted rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-primary transition-all"
                                                style={{ width: `${politician.promiseScore}%` }}
                                            />
                                        </div>
                                    </div>
                                    <div className="flex flex-wrap gap-4 text-sm">
                                        <span className="flex items-center gap-1">
                                            <span className="w-3 h-3 bg-green-500 rounded-full"></span>
                                            Kept: {kept}
                                        </span>
                                        <span className="flex items-center gap-1">
                                            <span className="w-3 h-3 bg-yellow-500 rounded-full"></span>
                                            In Progress: {inProgress}
                                        </span>
                                        <span className="flex items-center gap-1">
                                            <span className="w-3 h-3 bg-red-500 rounded-full"></span>
                                            Broken: {broken}
                                        </span>
                                    </div>
                                </>
                            )}
                        </CardContent>
                    </Card>

                    {/* Promise List */}
                    <div className="space-y-4">
                        {promises.map((promise: any, i: number) => (
                            <Card key={i}>
                                <CardContent className="p-5">
                                    <div className="flex items-start gap-3">
                                        <span className="text-2xl">
                                            {promise.status === "kept" && "✅"}
                                            {promise.status === "in_progress" && "⏳"}
                                            {promise.status === "broken" && "❌"}
                                        </span>
                                        <div>
                                            <h3 className="font-semibold">{promise.title}</h3>
                                            <p className="text-sm text-muted-foreground mt-1">
                                                Promised: {promise.year}
                                                {promise.delivered && ` · Delivered: ${promise.delivered}`}
                                            </p>
                                            <p className="text-sm mt-2">{promise.description}</p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        ))}
                        {promises.length === 0 && (
                            <div className="text-center py-8 text-muted-foreground">
                                No promises tracked yet.
                            </div>
                        )}
                    </div>
                </TabsContent>

                {/* Issues Tab */}
                <TabsContent value="issues">
                    <Card>
                        <CardContent className="p-6 text-center text-muted-foreground">
                            <p>No related issues found for this politician.</p>
                            <p className="mt-2">
                                <a
                                    href={`https://wa.me/2348160179151?text=I want to report an issue about ${politician.name}`}
                                    className="text-primary hover:underline"
                                >
                                    Report an issue via WhatsApp →
                                </a>
                            </p>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    );
}
