"use client";

import { useTheme } from "./theme-provider";

export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();

  const cycleTheme = () => {
    if (theme === "light") {
      setTheme("dark");
    } else if (theme === "dark") {
      setTheme("system");
    } else {
      setTheme("light");
    }
  };

  return (
    <button
      onClick={cycleTheme}
      className="relative w-10 h-10 rounded-full flex items-center justify-center
                 bg-foreground/5 hover:bg-foreground/10 transition-colors duration-300
                 border border-foreground/10 hover:border-foreground/20"
      aria-label={`Current theme: ${theme}. Click to change.`}
      title={`Theme: ${theme}`}
    >
      {/* Sun icon - visible in light mode */}
      <svg
        className={`w-5 h-5 absolute transition-all duration-500 ease-out-expo
                    ${resolvedTheme === "light" ? "opacity-100 rotate-0 scale-100" : "opacity-0 rotate-90 scale-50"}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
        />
      </svg>

      {/* Moon icon - visible in dark mode */}
      <svg
        className={`w-5 h-5 absolute transition-all duration-500 ease-out-expo
                    ${resolvedTheme === "dark" ? "opacity-100 rotate-0 scale-100" : "opacity-0 -rotate-90 scale-50"}`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={2}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
        />
      </svg>

      {/* System indicator dot */}
      {theme === "system" && (
        <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-mint rounded-full animate-pulse" />
      )}
    </button>
  );
}
