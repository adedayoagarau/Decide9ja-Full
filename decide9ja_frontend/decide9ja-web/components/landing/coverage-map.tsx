"use client";

import { useState } from "react";

// Simplified Nigeria map with state data
const states = [
    { name: "Lagos", status: "verified", zone: "South West" },
    { name: "Kano", status: "verified", zone: "North West" },
    { name: "Rivers", status: "verified", zone: "South South" },
    { name: "FCT", status: "verified", zone: "North Central" },
    { name: "Oyo", status: "verified", zone: "South West" },
    { name: "Kaduna", status: "verified", zone: "North West" },
    { name: "Anambra", status: "verified", zone: "South East" },
    { name: "Delta", status: "verified", zone: "South South" },
    { name: "Ogun", status: "verified", zone: "South West" },
    { name: "Enugu", status: "verified", zone: "South East" },
    { name: "Edo", status: "in-progress", zone: "South South" },
    { name: "Imo", status: "in-progress", zone: "South East" },
    { name: "Abia", status: "in-progress", zone: "South East" },
    { name: "Kwara", status: "in-progress", zone: "North Central" },
    { name: "Osun", status: "in-progress", zone: "South West" },
    { name: "Ekiti", status: "in-progress", zone: "South West" },
    { name: "Ondo", status: "in-progress", zone: "South West" },
    { name: "Benue", status: "in-progress", zone: "North Central" },
    { name: "Plateau", status: "in-progress", zone: "North Central" },
    { name: "Cross River", status: "in-progress", zone: "South South" },
];

const zones = [
    { name: "South West", count: 6, color: "bg-primary" },
    { name: "South South", count: 6, color: "bg-emerald-500" },
    { name: "South East", count: 5, color: "bg-teal-500" },
    { name: "North Central", count: 7, color: "bg-cyan-500" },
    { name: "North West", count: 7, color: "bg-blue-500" },
    { name: "North East", count: 6, color: "bg-purple-500" },
];

export function CoverageMap() {
    const [filter, setFilter] = useState<string>("all");

    const verifiedCount = states.filter(s => s.status === "verified").length;
    const inProgressCount = states.filter(s => s.status === "in-progress").length;

    const filteredStates = filter === "all"
        ? states
        : states.filter(s => s.status === filter);

    return (
        <section id="coverage" className="section-padding bg-secondary/20">
            <div className="container">
                <div className="text-center mb-16">
                    <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
                        Coverage
                    </h2>
                    <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
                        We're expanding across Nigeria. Coverage improves weekly.
                    </p>
                </div>

                <div className="max-w-5xl mx-auto">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                        {/* Map placeholder / Zone visualization */}
                        <div className="glass-card p-6 rounded-2xl">
                            <h3 className="text-lg font-semibold text-foreground mb-6">
                                Geopolitical Zones
                            </h3>
                            <div className="grid grid-cols-2 gap-4">
                                {zones.map((zone, index) => (
                                    <div key={index} className="flex items-center gap-3 p-3 rounded-lg bg-secondary/50">
                                        <div className={`w-3 h-3 rounded-full ${zone.color}`} />
                                        <div>
                                            <p className="text-sm font-medium text-foreground">{zone.name}</p>
                                            <p className="text-xs text-muted-foreground">{zone.count} states</p>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            {/* Nigeria outline placeholder */}
                            <div className="mt-6 aspect-square max-w-xs mx-auto relative">
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <span className="text-8xl opacity-20">🇳🇬</span>
                                </div>
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <div className="text-center">
                                        <p className="text-4xl font-bold text-primary">{verifiedCount + inProgressCount}</p>
                                        <p className="text-sm text-muted-foreground">States covered</p>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* State list */}
                        <div className="glass-card p-6 rounded-2xl">
                            <div className="flex items-center justify-between mb-6">
                                <h3 className="text-lg font-semibold text-foreground">
                                    State Coverage
                                </h3>
                                {/* Filter */}
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => setFilter("all")}
                                        className={`px-3 py-1 text-xs rounded-full transition-colors ${filter === "all"
                                                ? "bg-primary text-primary-foreground"
                                                : "bg-secondary text-muted-foreground"
                                            }`}
                                    >
                                        All
                                    </button>
                                    <button
                                        onClick={() => setFilter("verified")}
                                        className={`px-3 py-1 text-xs rounded-full transition-colors ${filter === "verified"
                                                ? "bg-primary text-primary-foreground"
                                                : "bg-secondary text-muted-foreground"
                                            }`}
                                    >
                                        Verified
                                    </button>
                                    <button
                                        onClick={() => setFilter("in-progress")}
                                        className={`px-3 py-1 text-xs rounded-full transition-colors ${filter === "in-progress"
                                                ? "bg-primary text-primary-foreground"
                                                : "bg-secondary text-muted-foreground"
                                            }`}
                                    >
                                        In Progress
                                    </button>
                                </div>
                            </div>

                            {/* Legend */}
                            <div className="flex gap-4 mb-4 text-xs text-muted-foreground">
                                <div className="flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-primary" />
                                    <span>Verified ({verifiedCount})</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <div className="w-2 h-2 rounded-full bg-yellow-500" />
                                    <span>In Progress ({inProgressCount})</span>
                                </div>
                            </div>

                            {/* State grid */}
                            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-[300px] overflow-y-auto">
                                {filteredStates.map((state, index) => (
                                    <div
                                        key={index}
                                        className="flex items-center gap-2 p-2 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors"
                                    >
                                        <div
                                            className={`w-2 h-2 rounded-full ${state.status === "verified"
                                                    ? "bg-primary"
                                                    : "bg-yellow-500"
                                                }`}
                                        />
                                        <span className="text-sm text-foreground truncate">
                                            {state.name}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}
