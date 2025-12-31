"use client";

import { useEffect, useState } from "react";

interface StatsCounterProps {
    value: number;
    label: string;
    duration?: number;
}

export function StatsCounter({ value, label, duration = 2000 }: StatsCounterProps) {
    const [count, setCount] = useState(0);

    useEffect(() => {
        let startTime: number;
        let animationFrame: number;

        const animate = (timestamp: number) => {
            if (!startTime) startTime = timestamp;
            const progress = Math.min((timestamp - startTime) / duration, 1);

            // Easing function for smooth animation
            const easeOutQuart = 1 - Math.pow(1 - progress, 4);
            setCount(Math.floor(easeOutQuart * value));

            if (progress < 1) {
                animationFrame = requestAnimationFrame(animate);
            }
        };

        animationFrame = requestAnimationFrame(animate);

        return () => cancelAnimationFrame(animationFrame);
    }, [value, duration]);

    return (
        <div className="text-center">
            <div className="text-4xl md:text-5xl font-bold text-primary">
                {count.toLocaleString()}
            </div>
            <div className="text-sm text-muted-foreground mt-1">{label}</div>
        </div>
    );
}
