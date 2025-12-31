"use client";

import { useState, useEffect } from "react";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { NIGERIAN_STATES, STATE_LGAS, api } from "@/lib/api";

interface LocationPickerProps {
    onLocationSelect: (state: string, lga: string) => void;
    showButton?: boolean;
    buttonText?: string;
}

export function LocationPicker({
    onLocationSelect,
    showButton = true,
    buttonText = "Find My Reps →",
}: LocationPickerProps) {
    const [states, setStates] = useState<string[]>(NIGERIAN_STATES);
    const [lgas, setLgas] = useState<string[]>([]);
    const [selectedState, setSelectedState] = useState("");
    const [selectedLga, setSelectedLga] = useState("");
    const [loading, setLoading] = useState(false);

    // Load states from API or use fallback
    useEffect(() => {
        api.locations.states().then(setStates).catch(() => setStates(NIGERIAN_STATES));
    }, []);

    // Load LGAs when state changes
    useEffect(() => {
        if (selectedState) {
            setSelectedLga("");
            api.locations
                .lgas(selectedState)
                .then(setLgas)
                .catch(() => setLgas(STATE_LGAS[selectedState] || []));
        } else {
            setLgas([]);
        }
    }, [selectedState]);

    const handleSubmit = () => {
        if (selectedState && selectedLga) {
            setLoading(true);
            onLocationSelect(selectedState, selectedLga);
        }
    };

    const handleGeolocation = () => {
        if ("geolocation" in navigator) {
            setLoading(true);
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    // In production, reverse geocode to get state/LGA
                    // For now, default to Lagos/Alimosho as demo
                    setSelectedState("Lagos");
                    setSelectedLga("Alimosho");
                    setLoading(false);
                },
                () => {
                    setLoading(false);
                    alert("Could not get your location. Please select manually.");
                }
            );
        }
    };

    return (
        <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* State Select */}
                <Select value={selectedState} onValueChange={setSelectedState}>
                    <SelectTrigger>
                        <SelectValue placeholder="Select State" />
                    </SelectTrigger>
                    <SelectContent>
                        {states.map((state) => (
                            <SelectItem key={state} value={state}>
                                {state}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>

                {/* LGA Select */}
                <Select
                    value={selectedLga}
                    onValueChange={setSelectedLga}
                    disabled={!selectedState}
                >
                    <SelectTrigger>
                        <SelectValue placeholder="Select LGA" />
                    </SelectTrigger>
                    <SelectContent>
                        {lgas.map((lga) => (
                            <SelectItem key={lga} value={lga}>
                                {lga}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {showButton && (
                <div className="flex flex-col sm:flex-row gap-3">
                    <Button
                        onClick={handleSubmit}
                        disabled={!selectedState || !selectedLga || loading}
                        className="flex-1 bg-primary hover:bg-primary/90"
                    >
                        {loading ? "Loading..." : buttonText}
                    </Button>

                    <Button
                        variant="outline"
                        onClick={handleGeolocation}
                        disabled={loading}
                        className="flex items-center gap-2"
                    >
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <circle cx="12" cy="12" r="3" />
                            <path d="M12 2v2" />
                            <path d="M12 20v2" />
                            <path d="m4.93 4.93 1.41 1.41" />
                            <path d="m17.66 17.66 1.41 1.41" />
                            <path d="M2 12h2" />
                            <path d="M20 12h2" />
                            <path d="m6.34 17.66-1.41 1.41" />
                            <path d="m19.07 4.93-1.41 1.41" />
                        </svg>
                        Use My Location
                    </Button>
                </div>
            )}
        </div>
    );
}
