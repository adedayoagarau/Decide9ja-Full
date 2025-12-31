"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LocationPicker } from "@/components/representatives/location-picker";
import { getPartyColor, Representative, api } from "@/lib/api";
import Link from "next/link";

// Demo data for when API is not available
const demoReps: Record<string, Representative[]> = {
    "Lagos-Alimosho": [
        {
            level: "federal",
            position: "President",
            politician: { id: "tinubu", name: "Bola Ahmed Tinubu", position: "President", party: "APC", state: "Federal", promiseScore: 23 },
        },
        {
            level: "federal",
            position: "Senator (Lagos West)",
            politician: { id: "sol", name: "Solomon Olamilekan Adeola", position: "Senator", party: "APC", state: "Lagos" },
        },
        {
            level: "federal",
            position: "House Rep (Alimosho Federal)",
            politician: { id: "odeneye", name: "Kehinde Joseph Odeneye", position: "House of Representatives", party: "APC", state: "Lagos" },
        },
        {
            level: "state",
            position: "Governor",
            politician: { id: "sanwoolu", name: "Babajide Olusola Sanwo-Olu", position: "Governor", party: "APC", state: "Lagos", promiseScore: 31 },
        },
        {
            level: "state",
            position: "State House (Alimosho I)",
            politician: { id: "yusuff", name: "Bisi Yusuff", position: "State House of Assembly", party: "APC", state: "Lagos" },
        },
        {
            level: "local",
            position: "LGA Chairman",
            politician: { id: "sulaimon", name: "Jelili Sulaimon", position: "LGA Chairman", party: "APC", state: "Lagos" },
        },
    ],
};

function RepresentativeCard({ rep }: { rep: Representative }) {
    return (
        <Card className="hover:shadow-md transition-shadow">
            <CardContent className="p-5">
                <div className="flex items-start gap-4">
                    {/* Avatar */}
                    <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center text-2xl shrink-0">
                        👤
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                        <div className="text-xs text-muted-foreground uppercase tracking-wide mb-1">
                            {rep.position}
                        </div>
                        <h3 className="font-semibold text-lg truncate">{rep.politician.name}</h3>
                        <Badge
                            style={{ backgroundColor: getPartyColor(rep.politician.party) }}
                            className="text-white mt-1"
                        >
                            {rep.politician.party}
                        </Badge>

                        {/* Promise Score */}
                        {rep.politician.promiseScore !== undefined && (
                            <div className="mt-3">
                                <div className="text-xs text-muted-foreground mb-1">
                                    Promise Score: {rep.politician.promiseScore}%
                                </div>
                                <div className="h-2 bg-muted rounded-full overflow-hidden w-32">
                                    <div
                                        className="h-full bg-primary"
                                        style={{ width: `${rep.politician.promiseScore}%` }}
                                    />
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Action */}
                    <Link href={`/politicians/${rep.politician.id}`}>
                        <Button variant="outline" size="sm">
                            View Profile →
                        </Button>
                    </Link>
                </div>
            </CardContent>
        </Card>
    );
}

function RepresentativesContent() {
    const searchParams = useSearchParams();
    const [state, setState] = useState(searchParams.get("state") || "");
    const [lga, setLga] = useState(searchParams.get("lga") || "");
    const [reps, setReps] = useState<Representative[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (state && lga) {
            setLoading(true);
            // Try API first, fallback to demo data
            api.representatives
                .byLocation(state, lga)
                .then(setReps)
                .catch(() => {
                    // Use demo data
                    const key = `${state}-${lga}`;
                    setReps(demoReps[key] || demoReps["Lagos-Alimosho"]);
                })
                .finally(() => setLoading(false));
        }
    }, [state, lga]);

    const handleLocationSelect = (newState: string, newLga: string) => {
        setState(newState);
        setLga(newLga);
        // Update URL
        window.history.pushState(null, "", `?state=${encodeURIComponent(newState)}&lga=${encodeURIComponent(newLga)}`);
    };

    const federalReps = reps.filter((r) => r.level === "federal");
    const stateReps = reps.filter((r) => r.level === "state");
    const localReps = reps.filter((r) => r.level === "local");

    return (
        <div className="container py-8 md:py-12">
            {/* Header */}
            <div className="max-w-2xl mb-8">
                <h1 className="text-3xl font-bold mb-2">Find Your Representatives</h1>
                <p className="text-muted-foreground">
                    Enter your location to see who represents you at every level of government.
                </p>
            </div>

            {/* Location Picker */}
            <Card className="mb-8">
                <CardContent className="p-6">
                    <LocationPicker onLocationSelect={handleLocationSelect} />
                </CardContent>
            </Card>

            {/* Results */}
            {state && lga && (
                <div className="space-y-8">
                    <div className="text-lg">
                        📍 Showing representatives for: <strong>{lga}, {state}</strong>
                    </div>

                    {loading ? (
                        <div className="text-center py-12 text-muted-foreground">
                            Loading representatives...
                        </div>
                    ) : (
                        <>
                            {/* Federal Level */}
                            {federalReps.length > 0 && (
                                <section>
                                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                                        🇳🇬 Federal Level
                                    </h2>
                                    <div className="space-y-4">
                                        {federalReps.map((rep, i) => (
                                            <RepresentativeCard key={i} rep={rep} />
                                        ))}
                                    </div>
                                </section>
                            )}

                            {/* State Level */}
                            {stateReps.length > 0 && (
                                <section>
                                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                                        🏛️ State Level
                                    </h2>
                                    <div className="space-y-4">
                                        {stateReps.map((rep, i) => (
                                            <RepresentativeCard key={i} rep={rep} />
                                        ))}
                                    </div>
                                </section>
                            )}

                            {/* Local Level */}
                            {localReps.length > 0 && (
                                <section>
                                    <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                                        🏘️ Local Level
                                    </h2>
                                    <div className="space-y-4">
                                        {localReps.map((rep, i) => (
                                            <RepresentativeCard key={i} rep={rep} />
                                        ))}
                                    </div>
                                </section>
                            )}

                            {/* Report Issue CTA */}
                            <Card className="bg-muted/50">
                                <CardContent className="p-6 text-center">
                                    <h3 className="font-semibold mb-2">📝 Report an Issue in {lga}</h3>
                                    <p className="text-muted-foreground text-sm mb-4">
                                        See a problem? Let us know. We&apos;ll track it and connect it to the responsible representatives.
                                    </p>
                                    <a href="https://wa.me/2348160179151?text=I want to report an issue">
                                        <Button>Report via WhatsApp</Button>
                                    </a>
                                </CardContent>
                            </Card>
                        </>
                    )}
                </div>
            )}

            {/* Empty State */}
            {!state && !lga && (
                <div className="text-center py-12 text-muted-foreground">
                    Enter your state and LGA above to see your representatives.
                </div>
            )}
        </div>
    );
}

export default function RepresentativesPage() {
    return (
        <Suspense fallback={<div className="container py-12 text-center">Loading...</div>}>
            <RepresentativesContent />
        </Suspense>
    );
}
