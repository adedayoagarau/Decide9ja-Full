"use client";

import { useState, useRef, useEffect } from "react";
import { sendChatMessage } from "@/lib/api";

interface Message {
  role: "user" | "assistant";
  content: string;
  tools_used?: string[];
}

export default function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
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
    setMessages((prev) => [...prev, { role: "user", content: msg }]);
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
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, I couldn't process that. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const suggestions = [
    "What issues are trending in Lagos?",
    "Explain the power crisis",
    "Compare APC vs PDP governors",
    "What bills are being debated?",
  ];

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 bg-c-green text-white w-14 h-14 rounded-full shadow-lg flex items-center justify-center hover:brightness-110 transition-all z-50"
        aria-label="Open chat with Tade"
      >
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
        </svg>
      </button>
    );
  }

  return (
    <div className="fixed bottom-0 right-0 md:bottom-6 md:right-6 w-full md:w-[400px] h-[80vh] md:h-[600px] bg-white border border-gray-300 md:rounded-lg shadow-2xl flex flex-col z-50 animate-slide-up">
      {/* Header */}
      <div className="bg-c-green text-white px-4 py-3 flex items-center justify-between md:rounded-t-lg flex-shrink-0">
        <div>
          <span className="font-bold text-sm">Ask Tade</span>
          <span className="text-[10px] ml-2 opacity-80 font-mono">AI Political Analyst</span>
        </div>
        <button onClick={() => setIsOpen(false)} className="hover:opacity-70 text-lg" aria-label="Close chat">
          &times;
        </button>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-gray-500 font-mono">
              Hi! I'm Tade, your AI political analyst. Ask me anything about Nigerian politics, issues, or bills.
            </p>
            <div className="space-y-2">
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(s)}
                  className="w-full text-left text-sm bg-gray-50 border border-gray-200 px-3 py-2 rounded hover:bg-c-yellow/20 hover:border-c-yellow transition-colors font-mono"
                >
                  &rarr; {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] px-3 py-2 text-sm leading-relaxed rounded ${
                msg.role === "user"
                  ? "bg-c-black text-white"
                  : "bg-gray-100 text-c-black"
              }`}
            >
              {msg.tools_used && msg.tools_used.length > 0 && (
                <div className="flex gap-1 mb-1 flex-wrap">
                  {msg.tools_used.map((tool, j) => (
                    <span key={j} className="text-[9px] bg-c-blue/20 text-c-blue px-1.5 py-0.5 rounded font-mono">
                      {tool}
                    </span>
                  ))}
                </div>
              )}
              <p className="whitespace-pre-wrap">{msg.content}</p>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 px-3 py-2 rounded text-sm">
              <span className="flex gap-1 items-center text-gray-400 font-mono">
                Analyzing
                <span className="flex gap-0.5">
                  <span className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1 h-1 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </span>
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-gray-200 flex flex-shrink-0">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask about politics, issues, bills..."
          className="flex-1 px-4 py-3 text-sm outline-none"
          aria-label="Chat message"
        />
        <button
          onClick={() => handleSend()}
          disabled={loading}
          className="bg-c-green text-white px-5 font-mono text-sm font-bold hover:brightness-110 disabled:opacity-50 transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  );
}
