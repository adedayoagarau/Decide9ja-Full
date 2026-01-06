"use client";

import { Button } from "@/components/ui/button";
import { useScrollProgress } from "@/hooks/use-scroll-reveal";

const WHATSAPP_LINK = "https://wa.me/2348160179151?text=Hi%20Tade";

export function Hero() {
    const scrollProgress = useScrollProgress();

    // Parallax values based on scroll
    const heroOpacity = Math.max(0, 1 - scrollProgress * 2);
    const heroScale = 1 - scrollProgress * 0.1;
    const headingY = scrollProgress * 100;
    const chatY = scrollProgress * 50;

    return (
        <section className="relative min-h-screen flex items-center justify-center pt-20 pb-16 overflow-hidden">
            {/* Animated background gradient */}
            <div
                className="absolute inset-0 transition-opacity duration-1000"
                style={{
                    background: `
                        radial-gradient(ellipse 80% 50% at 50% -20%, var(--mint-light) 0%, transparent 50%),
                        linear-gradient(to bottom, var(--background), var(--background))
                    `,
                    opacity: heroOpacity,
                }}
            />

            {/* Floating grid pattern */}
            <div
                className="absolute inset-0 opacity-[0.03] dark:opacity-[0.02]"
                style={{
                    backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23004737' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
                    transform: `translateY(${scrollProgress * 30}px)`,
                }}
            />

            {/* Floating orbs */}
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div
                    className="absolute w-96 h-96 rounded-full blur-3xl"
                    style={{
                        background: "var(--mint)",
                        opacity: 0.08,
                        top: "10%",
                        right: "-10%",
                        transform: `translate(${scrollProgress * 50}px, ${scrollProgress * 30}px)`,
                    }}
                />
                <div
                    className="absolute w-64 h-64 rounded-full blur-3xl"
                    style={{
                        background: "var(--primary)",
                        opacity: 0.05,
                        bottom: "20%",
                        left: "-5%",
                        transform: `translate(${-scrollProgress * 30}px, ${-scrollProgress * 20}px)`,
                    }}
                />
            </div>

            <div
                className="container relative z-10"
                style={{
                    opacity: heroOpacity,
                    transform: `scale(${heroScale})`,
                }}
            >
                <div className="max-w-4xl mx-auto text-center space-y-8">
                    {/* Badge */}
                    <div className="animate-fade-in-up">
                        <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium bg-mint-light/50 dark:bg-mint/10 text-primary dark:text-mint border border-primary/10 dark:border-mint/20">
                            <span className="w-2 h-2 rounded-full bg-mint animate-pulse" />
                            Nigeria&apos;s Civic Intelligence Platform
                        </span>
                    </div>

                    {/* Main heading with parallax */}
                    <h1
                        className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight animate-fade-in-up"
                        style={{
                            animationDelay: "0.1s",
                            transform: `translateY(${headingY * 0.3}px)`,
                        }}
                    >
                        Civic intelligence,{" "}
                        <span className="gradient-text relative">
                            on WhatsApp.
                            <svg
                                className="absolute -bottom-2 left-0 w-full h-3 text-mint/30"
                                viewBox="0 0 200 12"
                                preserveAspectRatio="none"
                            >
                                <path
                                    d="M0 9c50-6 100-6 200 0"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="3"
                                    strokeLinecap="round"
                                />
                            </svg>
                        </span>
                    </h1>

                    {/* Subheading */}
                    <p
                        className="text-lg md:text-xl lg:text-2xl text-muted-foreground max-w-2xl mx-auto animate-fade-in-up"
                        style={{ animationDelay: "0.2s" }}
                    >
                        Find your reps. Track their work. Report issues in your area.
                    </p>

                    {/* CTAs */}
                    <div
                        className="flex flex-col sm:flex-row items-center justify-center gap-4 animate-fade-in-up"
                        style={{ animationDelay: "0.3s" }}
                    >
                        <a
                            href={WHATSAPP_LINK}
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            <Button className="whatsapp-button pulse-glow text-base px-8 py-4 h-auto group">
                                <svg
                                    className="w-6 h-6 transition-transform duration-300 group-hover:scale-110"
                                    viewBox="0 0 24 24"
                                    fill="currentColor"
                                >
                                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                                </svg>
                                Message Tade on WhatsApp
                            </Button>
                        </a>
                        <a href="#demo">
                            <Button variant="outline" className="ghost-button text-base px-8 py-4 h-auto group">
                                See example answers
                                <svg
                                    className="w-4 h-4 transition-transform duration-300 group-hover:translate-x-1"
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                                </svg>
                            </Button>
                        </a>
                    </div>

                    {/* Trust chips */}
                    <div
                        className="flex flex-wrap items-center justify-center gap-3 animate-fade-in-up"
                        style={{ animationDelay: "0.4s" }}
                    >
                        {[
                            "No app download",
                            "Works on low-end phones",
                            "Neutral summaries"
                        ].map((text) => (
                            <span key={text} className="trust-chip">
                                <svg className="w-4 h-4 text-mint" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                                {text}
                            </span>
                        ))}
                    </div>
                </div>

                {/* Hero visual - Chat bubble mockup */}
                <div
                    className="mt-16 max-w-md mx-auto animate-fade-in-up"
                    style={{
                        animationDelay: "0.5s",
                        transform: `translateY(${chatY * 0.5}px)`,
                    }}
                >
                    <div className="glass-card p-1 rounded-3xl hover:shadow-lg transition-shadow duration-500">
                        <div className="bg-[#0b141a] rounded-2xl overflow-hidden">
                            {/* Chat header */}
                            <div className="bg-[#202c33] px-4 py-3 flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-mint/20 flex items-center justify-center">
                                    <span className="text-lg">🇳🇬</span>
                                </div>
                                <div className="flex-1">
                                    <p className="text-white font-medium text-sm">Tade • Decide9ja</p>
                                    <p className="text-[#8696a0] text-xs flex items-center gap-1">
                                        <span className="w-2 h-2 rounded-full bg-mint animate-pulse" />
                                        Online
                                    </p>
                                </div>
                                <div className="flex gap-4 text-[#8696a0]">
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                                    </svg>
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                                    </svg>
                                </div>
                            </div>

                            {/* Chat messages */}
                            <div className="p-4 space-y-3 min-h-[180px]">
                                {/* User message */}
                                <div className="flex justify-end animate-fade-in-up" style={{ animationDelay: "0.7s" }}>
                                    <div className="bg-[#005c4b] text-white text-sm px-3 py-2 rounded-lg rounded-tr-none max-w-[80%]">
                                        Who is my senator?
                                    </div>
                                </div>

                                {/* Typing indicator then response */}
                                <div className="flex justify-start animate-fade-in-up" style={{ animationDelay: "1s" }}>
                                    <div className="bg-[#202c33] text-white text-sm px-3 py-2 rounded-lg rounded-tl-none max-w-[85%]">
                                        <p className="mb-2">Your senator for Lagos West is <strong className="text-mint">Oluranti Adebule</strong> (APC).</p>
                                        <p className="text-[#8696a0]">Want to know more about her voting record?</p>
                                    </div>
                                </div>
                            </div>

                            {/* Input area */}
                            <div className="px-4 py-3 flex items-center gap-3 border-t border-[#202c33]">
                                <div className="flex-1 bg-[#2a3942] rounded-full px-4 py-2 text-[#8696a0] text-sm">
                                    Type a message<span className="animate-blink">|</span>
                                </div>
                                <div className="w-10 h-10 rounded-full bg-mint flex items-center justify-center">
                                    <svg className="w-5 h-5 text-[#0b141a]" fill="currentColor" viewBox="0 0 24 24">
                                        <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                                    </svg>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Scroll indicator */}
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2 animate-bounce">
                <span className="text-xs text-muted-foreground">Scroll to explore</span>
                <svg className="w-6 h-6 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                </svg>
            </div>
        </section>
    );
}
