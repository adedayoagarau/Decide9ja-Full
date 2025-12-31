"use client";

import { Button } from "@/components/ui/button";

const WHATSAPP_LINK = "https://wa.me/2348160179151?text=Hi%20Tade";

export function Hero() {
    return (
        <section className="relative min-h-screen flex items-center justify-center pt-20 pb-16 overflow-hidden">
            {/* Background gradient */}
            <div className="absolute inset-0 bg-gradient-to-b from-primary/5 via-background to-background" />

            {/* Subtle grid pattern */}
            <div
                className="absolute inset-0 opacity-[0.02]"
                style={{
                    backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
                }}
            />

            <div className="container relative z-10">
                <div className="max-w-4xl mx-auto text-center space-y-8">
                    {/* Main heading */}
                    <h1 className="text-4xl sm:text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight animate-fade-in-up">
                        Civic intelligence,{" "}
                        <span className="gradient-text">on WhatsApp.</span>
                    </h1>

                    {/* Subheading */}
                    <p className="text-lg md:text-xl lg:text-2xl text-muted-foreground max-w-2xl mx-auto animate-fade-in-up" style={{ animationDelay: "0.1s" }}>
                        Find your reps. Track their work. Report issues in your area.
                    </p>

                    {/* CTAs */}
                    <div className="flex flex-col sm:flex-row items-center justify-center gap-4 animate-fade-in-up" style={{ animationDelay: "0.2s" }}>
                        <a
                            href={WHATSAPP_LINK}
                            target="_blank"
                            rel="noopener noreferrer"
                        >
                            <Button className="whatsapp-button pulse-glow text-base px-8 py-4 h-auto">
                                <svg
                                    className="w-6 h-6"
                                    viewBox="0 0 24 24"
                                    fill="currentColor"
                                >
                                    <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                                </svg>
                                Message Tade on WhatsApp
                            </Button>
                        </a>
                        <a href="#demo">
                            <Button variant="outline" className="ghost-button text-base px-8 py-4 h-auto">
                                See example answers
                            </Button>
                        </a>
                    </div>

                    {/* Trust chips */}
                    <div className="flex flex-wrap items-center justify-center gap-3 animate-fade-in-up" style={{ animationDelay: "0.3s" }}>
                        <span className="trust-chip">
                            <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            No app download
                        </span>
                        <span className="trust-chip">
                            <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            Works on low-end phones
                        </span>
                        <span className="trust-chip">
                            <svg className="w-4 h-4 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                            Neutral summaries
                        </span>
                    </div>
                </div>

                {/* Hero visual - Chat bubble mockup */}
                <div className="mt-16 max-w-md mx-auto animate-fade-in-up animate-float" style={{ animationDelay: "0.4s" }}>
                    <div className="glass-card p-1 rounded-3xl">
                        <div className="bg-[#0b141a] rounded-2xl overflow-hidden">
                            {/* Chat header */}
                            <div className="bg-[#202c33] px-4 py-3 flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
                                    <span className="text-lg">🇳🇬</span>
                                </div>
                                <div>
                                    <p className="text-white font-medium text-sm">Tade • Decide9ja</p>
                                    <p className="text-[#8696a0] text-xs">Online</p>
                                </div>
                            </div>

                            {/* Chat messages */}
                            <div className="p-4 space-y-3">
                                {/* User message */}
                                <div className="flex justify-end">
                                    <div className="bg-[#005c4b] text-white text-sm px-3 py-2 rounded-lg rounded-tr-none max-w-[80%]">
                                        Who is my senator?
                                    </div>
                                </div>

                                {/* Bot response */}
                                <div className="flex justify-start">
                                    <div className="bg-[#202c33] text-white text-sm px-3 py-2 rounded-lg rounded-tl-none max-w-[85%]">
                                        <p className="mb-2">Your senator for Lagos West is <strong>Oluranti Adebule</strong> (APC).</p>
                                        <p className="text-[#8696a0]">Want to know more about her voting record?</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Scroll indicator */}
            <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
                <svg className="w-6 h-6 text-muted-foreground" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
                </svg>
            </div>
        </section>
    );
}
