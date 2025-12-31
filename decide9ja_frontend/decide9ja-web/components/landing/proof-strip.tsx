"use client";

import { useEffect, useState, useRef } from "react";

interface StatProps {
    value: number | string;
    label: string;
    suffix?: string;
}

function AnimatedStat({ value, label, suffix = "" }: StatProps) {
    const [displayValue, setDisplayValue] = useState(0);
    const [isVisible, setIsVisible] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setIsVisible(true);
                }
            },
            { threshold: 0.1 }
        );

        if (ref.current) {
            observer.observe(ref.current);
        }

        return () => observer.disconnect();
    }, []);

    useEffect(() => {
        if (!isVisible || typeof value !== "number") return;

        const duration = 2000;
        const steps = 60;
        const increment = value / steps;
        let current = 0;

        const timer = setInterval(() => {
            current += increment;
            if (current >= value) {
                setDisplayValue(value);
                clearInterval(timer);
            } else {
                setDisplayValue(Math.floor(current));
            }
        }, duration / steps);

        return () => clearInterval(timer);
    }, [isVisible, value]);

    const formattedValue = typeof value === "number"
        ? displayValue.toLocaleString() + suffix
        : value;

    return (
        <div ref={ref} className="stat-tile">
            <span className="text-3xl md:text-4xl font-bold text-foreground mb-2">
                {formattedValue}
            </span>
            <span className="text-sm text-muted-foreground text-center">
                {label}
            </span>
        </div>
    );
}

export function ProofStrip() {
    const stats = [
        { value: 1946, label: "Politicians indexed", suffix: "+" },
        { value: "Live", label: "WhatsApp bot" },
        { value: "Soon", label: "Web dashboard" },
    ];

    return (
        <section className="py-12 border-y border-border bg-secondary/30">
            <div className="container">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-3xl mx-auto">
                    {stats.map((stat, index) => (
                        <AnimatedStat
                            key={index}
                            value={stat.value}
                            label={stat.label}
                            suffix={stat.suffix}
                        />
                    ))}
                </div>
            </div>
        </section>
    );
}
