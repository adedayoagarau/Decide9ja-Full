"use client";

import { useState } from "react";

const faqs = [
    {
        question: "Is Decide9ja free to use?",
        answer: "Yes, Decide9ja is completely free. We believe civic information should be accessible to everyone. We're funded by grants and partnerships, not user fees.",
    },
    {
        question: "Where do you get your information?",
        answer: "We aggregate data from official sources like INEC, the National Assembly website, state assembly records, and verified news outlets. Every response cites its source so you can verify.",
    },
    {
        question: "Is Decide9ja politically biased?",
        answer: "No. We're committed to neutrality. Tade never endorses candidates or parties. We present facts and let you form your own opinions. Our team includes people from across the political spectrum.",
    },
    {
        question: "Can I report issues anonymously?",
        answer: "Yes. When you report a community issue, your identity is protected. We only share the location and description with relevant authorities, never your personal information.",
    },
    {
        question: "Is there a mobile app?",
        answer: "Not yet — and that's intentional. WhatsApp works on any phone, even low-end devices, without downloading anything new. We may build an app in the future, but our priority is reaching everyone.",
    },
    {
        question: "How can I contribute or volunteer?",
        answer: "We're always looking for help! You can contribute by verifying local politician data, reporting community issues, or joining our team. Message Tade with \"I want to help\" to get started.",
    },
];

export function FAQ() {
    const [openIndex, setOpenIndex] = useState<number | null>(null);

    const toggle = (index: number) => {
        setOpenIndex(openIndex === index ? null : index);
    };

    return (
        <section id="faq" className="section-padding">
            <div className="container">
                <div className="text-center mb-16">
                    <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
                        Frequently asked questions
                    </h2>
                    <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
                        Everything you need to know about Decide9ja
                    </p>
                </div>

                <div className="max-w-3xl mx-auto space-y-4">
                    {faqs.map((faq, index) => (
                        <div
                            key={index}
                            className="glass-card rounded-xl overflow-hidden"
                        >
                            <button
                                onClick={() => toggle(index)}
                                className="w-full px-6 py-4 flex items-center justify-between text-left hover:bg-secondary/30 transition-colors"
                            >
                                <span className="font-medium text-foreground pr-4">
                                    {faq.question}
                                </span>
                                <svg
                                    className={`w-5 h-5 text-muted-foreground flex-shrink-0 transition-transform duration-200 ${openIndex === index ? "rotate-180" : ""
                                        }`}
                                    fill="none"
                                    stroke="currentColor"
                                    viewBox="0 0 24 24"
                                >
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2}
                                        d="M19 9l-7 7-7-7"
                                    />
                                </svg>
                            </button>
                            <div
                                className={`px-6 overflow-hidden transition-all duration-200 ${openIndex === index
                                        ? "max-h-96 pb-4"
                                        : "max-h-0"
                                    }`}
                            >
                                <p className="text-muted-foreground text-sm leading-relaxed">
                                    {faq.answer}
                                </p>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </section>
    );
}
