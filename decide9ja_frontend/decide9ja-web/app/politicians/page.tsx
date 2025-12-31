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
import { PoliticianCard } from "@/components/politicians/politician-card";
import { Politician, api, NIGERIAN_STATES } from "@/lib/api";

// Demo politicians for when API is not available
const demoPoliticians: Politician[] = [
    { id: "tinubu", name: "Bola Ahmed Tinubu", position: "President", party: "APC", state: "Federal", promiseScore: 23 },
    { id: "sanwoolu", name: "Babajide Sanwo-Olu", position: "Governor", party: "APC", state: "Lagos", promiseScore: 31 },
    { id: "obi", name: "Peter Obi", position: "Former Governor", party: "LP", state: "Anambra" },
    { id: "atiku", name: "Atiku Abubakar", position: "Former Vice President", party: "PDP", state: "Adamawa" },
    { id: "wike", name: "Nyesom Wike", position: "FCT Minister", party: "PDP", state: "FCT" },
    { id: "akpabio", name: "Godswill Akpabio", position: "Senate President", party: "APC", state: "Akwa Ibom" },
    { id: "el-rufai", name: "Nasir El-Rufai", position: "Former Governor", party: "APC", state: "Kaduna" },
    { id: "adeleke", name: "Ademola Adeleke", position: "Governor", party: "PDP", state: "Osun", promiseScore: 28 },
    { id: "soludo", name: "Charles Soludo", position: "Governor", party: "APGA", state: "Anambra", promiseScore: 35 },
    { id: "makinde", name: "Seyi Makinde", position: "Governor", party: "PDP", state: "Oyo", promiseScore: 29 },
    { id: "ganduje", name: "Abdullahi Ganduje", position: "Former Governor", party: "APC", state: "Kano" },
    { id: "fubara", name: "Siminalayi Fubara", position: "Governor", party: "PDP", state: "Rivers", promiseScore: 22 },
];

export default function PoliticiansPage() {
    const [politicians, setPoliticians] = useState<Politician[]>(demoPoliticians);
    const [filtered, setFiltered] = useState<Politician[]>(demoPoliticians);
    const [search, setSearch] = useState("");
    const [partyFilter, setPartyFilter] = useState("all");
    const [stateFilter, setStateFilter] = useState("all");
    const [positionFilter, setPositionFilter] = useState("all");
    const [loading, setLoading] = useState(false);

    // Load from API
    useEffect(() => {
        setLoading(true);
        api.politicians
            .list()
            .then((data) => {
                if (data && data.length > 0) {
                    setPoliticians(data);
                    setFiltered(data);
                }
            })
            .catch(() => {
                // Use demo data
            })
            .finally(() => setLoading(false));
    }, []);

    // Filter politicians
    useEffect(() => {
        let result = politicians;

        if (search) {
            const q = search.toLowerCase();
            result = result.filter(
                (p) =>
                    p.name.toLowerCase().includes(q) ||
                    p.position.toLowerCase().includes(q)
            );
        }

        if (partyFilter !== "all") {
            result = result.filter((p) => p.party === partyFilter);
        }

        if (stateFilter !== "all") {
            result = result.filter((p) => p.state === stateFilter);
        }

        if (positionFilter !== "all") {
            result = result.filter((p) =>
                p.position.toLowerCase().includes(positionFilter.toLowerCase())
            );
        }

        setFiltered(result);
    }, [search, partyFilter, stateFilter, positionFilter, politicians]);

    // Get unique values for filters
    const parties = [...new Set(politicians.map((p) => p.party))].sort();
    const positions = [...new Set(politicians.map((p) => {
        if (p.position.includes("Governor")) return "Governor";
        if (p.position.includes("Senator")) return "Senator";
        if (p.position.includes("President")) return "President";
        if (p.position.includes("House")) return "House of Reps";
        return p.position;
    }))].sort();

    return (
        <div className="container py-8 md:py-12">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl font-bold mb-2">Politicians</h1>
                <p className="text-muted-foreground">
                    Browse {politicians.length} politicians tracked across Nigeria
                </p>
            </div>

            {/* Filters */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
                {/* Search */}
                <div className="lg:col-span-2">
                    <Input
                        placeholder="🔍 Search politicians..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>

                {/* Party */}
                <Select value={partyFilter} onValueChange={setPartyFilter}>
                    <SelectTrigger>
                        <SelectValue placeholder="Party" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Parties</SelectItem>
                        {parties.map((p) => (
                            <SelectItem key={p} value={p}>
                                {p}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>

                {/* State */}
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

                {/* Position */}
                <Select value={positionFilter} onValueChange={setPositionFilter}>
                    <SelectTrigger>
                        <SelectValue placeholder="Position" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Positions</SelectItem>
                        {positions.map((p) => (
                            <SelectItem key={p} value={p}>
                                {p}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {/* Results Count */}
            <div className="mb-6 text-muted-foreground">
                Showing {filtered.length} of {politicians.length} politicians
            </div>

            {/* Grid */}
            {loading ? (
                <div className="text-center py-12 text-muted-foreground">
                    Loading politicians...
                </div>
            ) : filtered.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
                    {filtered.map((politician) => (
                        <PoliticianCard key={politician.id} politician={politician} />
                    ))}
                </div>
            ) : (
                <div className="text-center py-12 text-muted-foreground">
                    No politicians found matching your filters.
                </div>
            )}
        </div>
    );
}
