import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Decide9ja - Nigerian Political Intelligence",
  description: "Track politicians, issues, bills, and elections. AI-powered civic transparency platform for Nigeria.",
  keywords: ["Nigeria", "politics", "transparency", "accountability", "elections", "budget", "corruption"],
  openGraph: {
    title: "Decide9ja - Nigerian Political Intelligence",
    description: "Track politicians, issues, bills, and elections.",
    type: "website",
    url: "https://decide9ja.com",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-c-beige">
        {children}
      </body>
    </html>
  );
}
