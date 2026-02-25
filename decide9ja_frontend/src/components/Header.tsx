"use client";

import { useState } from "react";
import { formatDate } from "@/lib/format";

const NAV_LINKS = [
  { href: "/", label: "HOME" },
  { href: "/issues", label: "ISSUES" },
  { href: "/explore", label: "EXPLORE" },
  { href: "/chat", label: "ASK TADE" },
  { href: "/admin", label: "DASHBOARD" },
  { href: "/about", label: "ABOUT" },
];

export default function Header() {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="bg-c-black text-gray-500 px-4 md:px-8 py-4 md:py-5 flex justify-between items-center font-display text-xs tracking-wide border-b border-c-border sticky top-0 z-40">
      <a
        href="/"
        className="text-white font-normal text-xs tracking-[0.2em] uppercase hover:text-gray-300 transition-colors"
      >
        Decide9ja
      </a>

      {/* Desktop nav */}
      <nav className="hidden md:flex gap-8 lg:gap-14 text-xs items-center">
        {NAV_LINKS.map((link) => (
          <a
            key={link.href}
            href={link.href}
            className="text-gray-500 hover:text-white transition-colors"
          >
            {link.label}
          </a>
        ))}
        <span className="text-gray-600 font-mono">{formatDate()}</span>
      </nav>

      {/* Mobile hamburger */}
      <button
        onClick={() => setMenuOpen(!menuOpen)}
        className="md:hidden text-white p-1"
        aria-label="Toggle navigation"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          {menuOpen ? (
            <path d="M6 6l12 12M6 18L18 6" />
          ) : (
            <path d="M3 6h18M3 12h18M3 18h18" />
          )}
        </svg>
      </button>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="absolute top-full left-0 right-0 bg-c-black border-b border-c-border md:hidden z-50 animate-fade-in">
          <nav className="flex flex-col px-4 py-3 gap-1">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-gray-400 hover:text-white py-2 text-sm transition-colors"
                onClick={() => setMenuOpen(false)}
              >
                {link.label}
              </a>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
}
