import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { ThemeProvider } from "@/components/theme/theme-provider";

const inter = Inter({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Decide9ja - Civic Intelligence on WhatsApp",
  description:
    "Find your representatives, track their work, and report issues in your community. Nigeria's civic information platform on WhatsApp.",
  keywords: [
    "Nigeria politics",
    "Nigerian politicians",
    "civic engagement",
    "WhatsApp bot",
    "INEC",
    "governors",
    "senators",
    "house of representatives",
    "accountability",
    "Tade",
    "Decide9ja",
  ],
  openGraph: {
    title: "Decide9ja - Civic Intelligence on WhatsApp",
    description:
      "Find your reps. Track their work. Report issues in your area.",
    type: "website",
    locale: "en_NG",
    siteName: "Decide9ja",
  },
  twitter: {
    card: "summary_large_image",
    title: "Decide9ja - Civic Intelligence on WhatsApp",
    description:
      "Find your reps. Track their work. Report issues in your area.",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Prevent flash of unstyled content */}
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var theme = localStorage.getItem('decide9ja-theme');
                  var resolved = theme;
                  if (!theme || theme === 'system') {
                    resolved = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
                  }
                  document.documentElement.classList.add(resolved);
                } catch (e) {
                  document.documentElement.classList.add('dark');
                }
              })();
            `,
          }}
        />
      </head>
      <body
        className={`${inter.variable} antialiased min-h-screen flex flex-col`}
      >
        <ThemeProvider>
          <Header />
          <main className="flex-1">{children}</main>
          <Footer />
        </ThemeProvider>
      </body>
    </html>
  );
}
