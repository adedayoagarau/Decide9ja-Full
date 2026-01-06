"use client";

import { useScrollReveal } from "@/hooks/use-scroll-reveal";

const features = [
    {
        title: "Find my representatives",
        description: "Know who represents you at federal, state, and local government levels.",
        icon: (
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
        ),
        color: "from-emerald-500/20 to-transparent",
    },
    {
        title: "Politician records",
        description: "Access bills sponsored, motions moved, and committee memberships.",
        icon: (
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
        ),
        color: "from-blue-500/20 to-transparent",
    },
    {
        title: "Track bills and motions",
        description: "Follow legislation that matters to you through the National Assembly.",
        icon: (
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4" />
            </svg>
        ),
        color: "from-violet-500/20 to-transparent",
    },
    {
        title: "Political news, explained",
        description: "Get neutral summaries of current political events and debates.",
        icon: (
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
            </svg>
        ),
        color: "from-amber-500/20 to-transparent",
    },
    {
        title: "Report a community issue",
        description: "Document problems like bad roads, power outages, or security concerns.",
        icon: (
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
        ),
        color: "from-rose-500/20 to-transparent",
    },
    {
        title: "Voter registration guidance",
        description: "Step-by-step help to register, get your PVC, and verify your status.",
        icon: (
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
        ),
        color: "from-cyan-500/20 to-transparent",
    },
];

function FeatureCard({ feature, index }: { feature: typeof features[0]; index: number }) {
    const [cardRef, isInView] = useScrollReveal<HTMLDivElement>({ threshold: 0.2 });

    return (
        <div
            ref={cardRef}
            className={`feature-card group relative overflow-hidden transition-all duration-700 ${
                isInView
                    ? "opacity-100 translate-y-0"
                    : "opacity-0 translate-y-12"
            }`}
            style={{ transitionDelay: `${index * 100}ms` }}
        >
            {/* Gradient background on hover */}
            <div className={`absolute inset-0 bg-gradient-to-br ${feature.color} opacity-0 group-hover:opacity-100 transition-opacity duration-500`} />

            {/* Icon */}
            <div className="relative w-12 h-12 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-4 group-hover:bg-primary group-hover:text-primary-foreground transition-all duration-300 group-hover:scale-110">
                {feature.icon}
            </div>

            {/* Content */}
            <h3 className="relative text-lg font-semibold text-foreground mb-2 group-hover:text-primary dark:group-hover:text-mint transition-colors duration-300">
                {feature.title}
            </h3>
            <p className="relative text-muted-foreground text-sm leading-relaxed">
                {feature.description}
            </p>

            {/* Arrow indicator on hover */}
            <div className="relative mt-4 flex items-center gap-2 text-sm text-primary dark:text-mint opacity-0 group-hover:opacity-100 transition-all duration-300 translate-x-0 group-hover:translate-x-2">
                <span>Learn more</span>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
            </div>
        </div>
    );
}

export function FeaturesGrid() {
    const [headerRef, isHeaderInView] = useScrollReveal<HTMLDivElement>();

    return (
        <section id="features" className="section-padding bg-gradient-to-b from-background via-secondary/10 to-background">
            <div className="container">
                {/* Section header */}
                <div
                    ref={headerRef}
                    className={`text-center mb-16 transition-all duration-700 ${
                        isHeaderInView
                            ? "opacity-100 translate-y-0"
                            : "opacity-0 translate-y-8"
                    }`}
                >
                    <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium bg-primary/10 text-primary dark:text-mint mb-4">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        Capabilities
                    </span>
                    <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-foreground mb-4">
                        What you can do
                    </h2>
                    <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
                        Everything you need to engage with Nigerian democracy, all through WhatsApp
                    </p>
                </div>

                {/* Features grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto">
                    {features.map((feature, index) => (
                        <FeatureCard key={index} feature={feature} index={index} />
                    ))}
                </div>

                {/* Bottom CTA */}
                <div
                    className={`text-center mt-12 transition-all duration-700 delay-500 ${
                        isHeaderInView ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"
                    }`}
                >
                    <p className="text-muted-foreground text-sm">
                        More features coming soon •{" "}
                        <a href="#" className="text-primary dark:text-mint hover:underline">
                            Request a feature
                        </a>
                    </p>
                </div>
            </div>
        </section>
    );
}
