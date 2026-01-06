"use client";

import { useEffect, useState, useRef } from "react";
import { useScrollReveal } from "@/hooks/use-scroll-reveal";

interface StatProps {
    value: number | string;
    label: string;
    suffix?: string;
    delay?: number;
}

function AnimatedStat({ value, label, suffix = "", delay = 0 }: StatProps) {
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

        // Add delay before starting animation
        const timeout = setTimeout(() => {
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
        }, delay);

        return () => clearTimeout(timeout);
    }, [isVisible, value, delay]);

    const formattedValue = typeof value === "number"
        ? displayValue.toLocaleString() + suffix
        : value;

    return (
        <div
            ref={ref}
            className="stat-tile group hover:border-primary/30 transition-all duration-500"
        >
            <span className="text-3xl md:text-4xl font-bold text-foreground mb-2 tabular-nums">
                {formattedValue}
            </span>
            <span className="text-sm text-muted-foreground text-center">
                {label}
            </span>
            {/* Subtle hover glow */}
            <div className="absolute inset-0 rounded-xl bg-primary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500 -z-10" />
        </div>
    );
}

export function ProofStrip() {
    const [sectionRef, isInView] = useScrollReveal<HTMLElement>();

    const stats = [
        { value: 1946, label: "Politicians indexed", suffix: "+" },
        { value: "Live", label: "WhatsApp bot" },
        { value: "Soon", label: "Web dashboard" },
    ];

    return (
        <section
            ref={sectionRef}
            className={`py-16 border-y border-border bg-gradient-to-b from-background to-secondary/20 transition-all duration-700 ${
                isInView ? "opacity-100" : "opacity-0 translate-y-8"
            }`}
        >
            <div className="container">
                {/* Section header */}
                <p className="text-center text-sm font-medium text-muted-foreground uppercase tracking-wider mb-8">
                    Trusted civic data
                </p>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto">
                    {stats.map((stat, index) => (
                        <AnimatedStat
                            key={index}
                            value={stat.value}
                            label={stat.label}
                            suffix={stat.suffix}
                            delay={index * 200}
                        />
                    ))}
                </div>

                {/* Decorative line */}
                <div className="flex items-center justify-center gap-4 mt-10">
                    <div className="h-px w-20 bg-gradient-to-r from-transparent to-border" />
                    <span className="text-xs text-muted-foreground">Powered by open data</span>
                    <div className="h-px w-20 bg-gradient-to-l from-transparent to-border" />
                </div>
            </div>
        </section>
    );
}
