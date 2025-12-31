"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

const WHATSAPP_LINK = "https://wa.me/2348160179151?text=Hi%20Tade";

const conversations = [
    {
        id: 1,
        messages: [
            { role: "user", text: "Who is my senator?" },
            { role: "bot", text: "Which state and LGA are you in?" },
            { role: "user", text: "Lagos, Ikeja" },
            { role: "bot", text: "Your senator for Lagos Central is **Wasiu Eshinlokun-Sanni** (APC). He was sworn in December 2023 after winning a rerun election.\n\nWant to know about his sponsored bills?" },
        ],
    },
    {
        id: 2,
        messages: [
            { role: "user", text: "What's happening with the tax reform bill?" },
            { role: "bot", text: "The **Nigeria Tax Reform Bills** include 4 bills currently in the National Assembly:\n\n1. Nigeria Tax Bill\n2. Tax Administration Bill\n3. NRS Bill\n4. Joint Revenue Board Bill\n\nThe main controversy is over VAT distribution — Northern governors oppose it, saying it favors Lagos and Rivers.\n\nWant details on any specific bill?" },
        ],
    },
    {
        id: 3,
        messages: [
            { role: "user", text: "Report a bad road" },
            { role: "bot", text: "I'll help you document this. Where is the road located?" },
            { role: "user", text: "Allen Avenue, Ikeja, Lagos" },
            { role: "bot", text: "**Documented:**\n• Bad road at Allen Avenue, Ikeja\n• Flagged to Lagos State Works Ministry\n\nYou'll get updates when there's action. Anything else?" },
        ],
    },
    {
        id: 4,
        messages: [
            { role: "user", text: "Latest news on Tinubu" },
            { role: "bot", text: "Here's the latest on **President Bola Tinubu**:\n\n• Presented ₦47.9 trillion 2025 budget to NASS\n• Announced new national minimum wage of ₦70,000\n• Facing pushback on tax reform from Northern governors\n\nWant details on any of these?" },
        ],
    },
];

const prompts = [
    "Who is my senator?",
    "Tax reform bill update",
    "Report a bad road",
    "Governor of my state",
];

export function LiveDemo() {
    const [activeConvo, setActiveConvo] = useState(0);

    return (
        <section id="demo" className="section-padding">
            <div className="container">
                <div className="text-center mb-16">
                    <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
                        Live demo
                    </h2>
                    <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
                        See how Tade helps Nigerians engage with democracy
                    </p>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 max-w-6xl mx-auto">
                    {/* Chat transcript carousel */}
                    <div className="glass-card p-1 rounded-3xl">
                        <div className="bg-[#0b141a] rounded-2xl overflow-hidden">
                            {/* Chat header */}
                            <div className="bg-[#202c33] px-4 py-3 flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
                                    <span className="text-lg">🇳🇬</span>
                                </div>
                                <div className="flex-1">
                                    <p className="text-white font-medium text-sm">Tade • Decide9ja</p>
                                    <p className="text-[#8696a0] text-xs">Online</p>
                                </div>
                                {/* Carousel dots */}
                                <div className="flex gap-1.5">
                                    {conversations.map((_, index) => (
                                        <button
                                            key={index}
                                            onClick={() => setActiveConvo(index)}
                                            className={`w-2 h-2 rounded-full transition-colors ${activeConvo === index
                                                    ? "bg-primary"
                                                    : "bg-[#8696a0]/50"
                                                }`}
                                        />
                                    ))}
                                </div>
                            </div>

                            {/* Chat messages */}
                            <div className="p-4 space-y-3 min-h-[300px]">
                                {conversations[activeConvo].messages.map((msg, index) => (
                                    <div
                                        key={index}
                                        className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                                    >
                                        <div
                                            className={`text-sm px-3 py-2 rounded-lg max-w-[85%] ${msg.role === "user"
                                                    ? "bg-[#005c4b] text-white rounded-tr-none"
                                                    : "bg-[#202c33] text-white rounded-tl-none"
                                                }`}
                                        >
                                            <p
                                                className="whitespace-pre-line"
                                                dangerouslySetInnerHTML={{
                                                    __html: msg.text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                                                }}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Prompts and CTA */}
                    <div className="flex flex-col justify-center space-y-8">
                        <div>
                            <h3 className="text-xl font-semibold text-foreground mb-4">
                                Try these prompts
                            </h3>
                            <div className="flex flex-wrap gap-3">
                                {prompts.map((prompt, index) => (
                                    <button
                                        key={index}
                                        onClick={() => setActiveConvo(index)}
                                        className={`px-4 py-2 rounded-full text-sm transition-all ${activeConvo === index
                                                ? "bg-primary text-primary-foreground"
                                                : "bg-secondary text-muted-foreground hover:bg-secondary/80"
                                            }`}
                                    >
                                        {prompt}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <div className="space-y-4">
                            <p className="text-muted-foreground">
                                Ready to try it yourself? Message Tade on WhatsApp and get answers about Nigerian politics in seconds.
                            </p>
                            <a
                                href={WHATSAPP_LINK}
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                <Button className="whatsapp-button">
                                    <svg
                                        className="w-5 h-5"
                                        viewBox="0 0 24 24"
                                        fill="currentColor"
                                    >
                                        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                                    </svg>
                                    Open WhatsApp
                                </Button>
                            </a>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    );
}
