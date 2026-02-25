"use client";

import { useState, useRef, useEffect } from "react";
import Header from "@/components/Header";
import { sendChatMessage } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  tools_used?: string[];
  timestamp: number;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = async (text?: string) => {
    const msg = text || input.trim();
    if (!msg || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: msg, timestamp: Date.now() }]);
    setLoading(true);

    try {
      const data = await sendChatMessage(msg, sessionId || undefined);
      if (data.session_id) setSessionId(data.session_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.response,
          tools_used: data.tools_used,
          timestamp: Date.now(),
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "I couldn't process that request. Please try again.", timestamp: Date.now() },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const suggestions = [
    "What are the biggest issues in Nigeria right now?",
    "Explain the power crisis in simple terms",
    "What bills are currently being debated?",
    "Compare roads spending across states",
    "Who are the key politicians in Lagos?",
    "What happened with ASUU this year?",
  ];

  return (
    <div className="min-h-screen bg-c-beige flex flex-col">
      <Header />

      <div className="flex-1 flex flex-col max-w-4xl mx-auto w-full">
        {/* Messages area */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-4">
          {messages.length === 0 && (
            <div className="py-12">
              <div className="text-center mb-8">
                <h1 className="text-3xl md:text-4xl font-bold mb-2">Ask Tade</h1>
                <p className="text-gray-500 font-mono text-sm">
                  AI-powered Nigerian political analyst. Ask anything.
                </p>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-2xl mx-auto">
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(s)}
                    className="text-left bg-white border border-gray-200 px-4 py-3 text-sm hover:border-c-green hover:bg-c-green/5 transition-colors"
                  >
                    <span className="text-c-green mr-2">&rarr;</span>
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"} animate-fade-in`}>
              <div className={`max-w-[80%] ${msg.role === "user" ? "bg-c-black text-white" : "bg-white border border-gray-200"} px-4 py-3 rounded-sm`}>
                {msg.tools_used && msg.tools_used.length > 0 && (
                  <div className="flex gap-1 mb-2 flex-wrap">
                    {msg.tools_used.map((tool, j) => (
                      <span key={j} className="text-[9px] bg-c-blue/20 text-c-blue px-1.5 py-0.5 rounded font-mono">
                        {tool}
                      </span>
                    ))}
                  </div>
                )}
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start animate-fade-in">
              <div className="bg-white border border-gray-200 px-4 py-3 rounded-sm">
                <span className="flex gap-1 items-center text-gray-400 font-mono text-sm">
                  Tade is thinking
                  <span className="flex gap-0.5 ml-1">
                    <span className="w-1.5 h-1.5 bg-c-green rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 bg-c-green rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 bg-c-green rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </span>
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Input bar */}
        <div className="border-t border-gray-300 bg-white px-4 md:px-8 py-4 flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSend()}
            placeholder="Ask about politics, issues, bills, budgets..."
            className="flex-1 text-sm outline-none py-2"
            aria-label="Chat message"
          />
          <button
            onClick={() => handleSend()}
            disabled={loading || !input.trim()}
            className="bg-c-green text-white px-6 py-2 font-mono text-sm uppercase hover:brightness-110 disabled:opacity-40 transition-colors"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
