# DECIDE9JA WEB DASHBOARD - ANTIGRAVITY BUILD PROMPT

## Overview

Build a Next.js web dashboard for Decide9ja, a Nigerian civic information platform. The dashboard complements the WhatsApp chatbot, providing a web interface for citizens to find their representatives, track political issues, and hold politicians accountable.

---

## Tech Stack

- **Framework**: Next.js 14 (App Router)
- **Styling**: Tailwind CSS + shadcn/ui
- **Charts**: Recharts
- **Maps**: react-simple-maps (for Nigeria map)
- **State**: React Query (TanStack Query)
- **Icons**: Lucide React
- **Deployment**: Vercel

---

## Project Setup

```bash
npx create-next-app@latest decide9ja-web --typescript --tailwind --eslint --app --src-dir=false
cd decide9ja-web
npx shadcn@latest init
npx shadcn@latest add button card input select badge avatar tabs dialog dropdown-menu sheet skeleton separator
npm install @tanstack/react-query recharts react-simple-maps lucide-react
```

---

## File Structure

Create these files:

```
decide9ja-web/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── globals.css
│   ├── politicians/
│   │   ├── page.tsx
│   │   └── [id]/
│   │       └── page.tsx
│   ├── representatives/
│   │   └── page.tsx
│   ├── issues/
│   │   ├── page.tsx
│   │   └── [id]/
│   │       └── page.tsx
│   └── admin/
│       ├── layout.tsx
│       └── page.tsx
├── components/
│   ├── layout/
│   │   ├── header.tsx
│   │   ├── footer.tsx
│   │   └── mobile-nav.tsx
│   ├── politicians/
│   │   ├── politician-card.tsx
│   │   ├── politician-grid.tsx
│   │   └── promise-tracker.tsx
│   ├── representatives/
│   │   ├── location-picker.tsx
│   │   └── rep-card.tsx
│   ├── issues/
│   │   └── issue-card.tsx
│   ├── maps/
│   │   └── nigeria-map.tsx
│   ├── charts/
│   │   └── message-chart.tsx
│   └── shared/
│       ├── stats-counter.tsx
│       ├── whatsapp-cta.tsx
│       └── search-bar.tsx
├── lib/
│   ├── api.ts
│   ├── utils.ts
│   ├── constants.ts
│   └── types.ts
└── hooks/
    ├── use-politicians.ts
    └── use-representatives.ts
```

---

## Implementation

### 1. Root Layout (app/layout.tsx)

```tsx
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { QueryProvider } from "@/components/providers/query-provider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Decide9ja - Know Your Representatives",
  description: "Nigeria's civic information platform. Find your representatives, track promises, report issues.",
  keywords: ["Nigeria", "politics", "representatives", "civic", "government", "accountability"],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <QueryProvider>
          <div className="min-h-screen flex flex-col">
            <Header />
            <main className="flex-1">{children}</main>
            <Footer />
          </div>
        </QueryProvider>
      </body>
    </html>
  );
}
```

### 2. Header Component (components/layout/header.tsx)

```tsx
"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X, Search, MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";

const navItems = [
  { href: "/politicians", label: "Politicians" },
  { href: "/issues", label: "Issues" },
  { href: "/representatives", label: "Find My Reps" },
];

export function Header() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-white/95 backdrop-blur">
      <div className="container flex h-16 items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center space-x-2">
          <span className="text-2xl">🇳🇬</span>
          <span className="font-bold text-xl text-green-700">Decide9ja</span>
        </Link>

        {/* Desktop Navigation */}
        <nav className="hidden md:flex items-center space-x-6">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-sm font-medium text-gray-600 hover:text-green-700 transition-colors"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        {/* Desktop Actions */}
        <div className="hidden md:flex items-center space-x-4">
          <Button variant="outline" size="sm">
            <Search className="h-4 w-4 mr-2" />
            Search
          </Button>
          <Button className="bg-green-600 hover:bg-green-700">
            <MessageCircle className="h-4 w-4 mr-2" />
            WhatsApp
          </Button>
        </div>

        {/* Mobile Menu */}
        <Sheet open={isOpen} onOpenChange={setIsOpen}>
          <SheetTrigger asChild className="md:hidden">
            <Button variant="ghost" size="icon">
              <Menu className="h-6 w-6" />
            </Button>
          </SheetTrigger>
          <SheetContent side="right" className="w-[300px]">
            <nav className="flex flex-col space-y-4 mt-8">
              {navItems.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="text-lg font-medium text-gray-600 hover:text-green-700"
                  onClick={() => setIsOpen(false)}
                >
                  {item.label}
                </Link>
              ))}
              <Button className="bg-green-600 hover:bg-green-700 mt-4">
                <MessageCircle className="h-4 w-4 mr-2" />
                Open WhatsApp
              </Button>
            </nav>
          </SheetContent>
        </Sheet>
      </div>
    </header>
  );
}
```

### 3. Landing Page (app/page.tsx)

```tsx
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { LocationPicker } from "@/components/representatives/location-picker";
import { StatsCounter } from "@/components/shared/stats-counter";
import { IssueCard } from "@/components/issues/issue-card";
import { PoliticianCard } from "@/components/politicians/politician-card";
import { MapPin, Users, FileText, MessageCircle, ChevronRight } from "lucide-react";

export default function HomePage() {
  return (
    <div className="flex flex-col">
      {/* Hero Section */}
      <section className="bg-gradient-to-b from-green-50 to-white py-16 md:py-24">
        <div className="container text-center">
          <h1 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
            Know Your Representatives.
            <br />
            <span className="text-green-700">Hold Them Accountable.</span>
          </h1>
          <p className="text-lg text-gray-600 mb-8 max-w-2xl mx-auto">
            Nigeria's civic information platform. Find your reps, track promises, report issues.
          </p>

          {/* Location Picker */}
          <Card className="max-w-xl mx-auto">
            <CardContent className="p-6">
              <h2 className="text-lg font-semibold mb-4">Find Your Representatives</h2>
              <LocationPicker />
            </CardContent>
          </Card>

          {/* WhatsApp CTA */}
          <div className="mt-8 flex items-center justify-center space-x-2 text-gray-500">
            <span>or use</span>
            <Button variant="link" className="text-green-600 p-0">
              <MessageCircle className="h-4 w-4 mr-1" />
              WhatsApp
            </Button>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="py-12 border-y bg-white">
        <div className="container">
          <div className="grid grid-cols-3 gap-8 text-center">
            <StatsCounter value={505} label="Politicians Tracked" icon={<Users />} />
            <StatsCounter value={36} label="States Covered" icon={<MapPin />} />
            <StatsCounter value={1247} label="Issues Reported" icon={<FileText />} />
          </div>
        </div>
      </section>

      {/* Trending Issues */}
      <section className="py-16 bg-gray-50">
        <div className="container">
          <div className="flex items-center justify-between mb-8">
            <h2 className="text-2xl font-bold">Trending Issues</h2>
            <Link href="/issues" className="text-green-600 hover:underline flex items-center">
              View All <ChevronRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            <IssueCard
              id="1"
              title="National Grid Collapse #7"
              domain="Power"
              severity="severe"
              location="Nationwide"
              updatedAt="2 hours ago"
              eventCount={12}
              evidenceCount={8}
            />
            <IssueCard
              id="2"
              title="Lagos-Ibadan Expressway Delays"
              domain="Infrastructure"
              severity="moderate"
              location="Lagos, Ogun"
              updatedAt="1 day ago"
              eventCount={24}
              evidenceCount={15}
            />
            <IssueCard
              id="3"
              title="Kaduna Rail Safety Concerns"
              domain="Security"
              severity="moderate"
              location="Kaduna, FCT"
              updatedAt="3 days ago"
              eventCount={5}
              evidenceCount={2}
            />
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-16">
        <div className="container">
          <h2 className="text-2xl font-bold text-center mb-12">How It Works</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
                <MapPin className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="font-semibold mb-2">1. Enter Your Location</h3>
              <p className="text-gray-600">Select your state and LGA to find your representatives.</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
                <Users className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="font-semibold mb-2">2. See Your Reps</h3>
              <p className="text-gray-600">View all your representatives from federal to local level.</p>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-4">
                <FileText className="h-8 w-8 text-green-600" />
              </div>
              <h3 className="font-semibold mb-2">3. Track & Report</h3>
              <p className="text-gray-600">Track promises, report issues, hold them accountable.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Featured Politicians */}
      <section className="py-16 bg-gray-50">
        <div className="container">
          <div className="flex items-center justify-between mb-8">
            <h2 className="text-2xl font-bold">Featured Politicians</h2>
            <Link href="/politicians" className="text-green-600 hover:underline flex items-center">
              View All <ChevronRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <PoliticianCard
              id="1"
              name="Bola Tinubu"
              position="President"
              party="APC"
              state="Federal"
              promiseScore={23}
            />
            <PoliticianCard
              id="2"
              name="Babajide Sanwo-Olu"
              position="Governor"
              party="APC"
              state="Lagos"
              promiseScore={31}
            />
            <PoliticianCard
              id="3"
              name="Peter Obi"
              position="LP Leader"
              party="LP"
              state="Anambra"
            />
            <PoliticianCard
              id="4"
              name="Atiku Abubakar"
              position="PDP Leader"
              party="PDP"
              state="Adamawa"
            />
          </div>
        </div>
      </section>

      {/* WhatsApp CTA */}
      <section className="py-16 bg-green-700 text-white">
        <div className="container text-center">
          <h2 className="text-2xl font-bold mb-4">Prefer WhatsApp?</h2>
          <p className="mb-6 text-green-100">
            Ask about your representatives, report issues, get updates - all on WhatsApp.
          </p>
          <Button size="lg" variant="secondary">
            <MessageCircle className="h-5 w-5 mr-2" />
            Open WhatsApp
          </Button>
        </div>
      </section>
    </div>
  );
}
```

### 4. Location Picker (components/representatives/location-picker.tsx)

```tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { MapPin, Loader2 } from "lucide-react";
import { STATES, LGAS } from "@/lib/constants";

export function LocationPicker() {
  const router = useRouter();
  const [state, setState] = useState("");
  const [lga, setLga] = useState("");
  const [isLocating, setIsLocating] = useState(false);

  const availableLgas = state ? LGAS[state] || [] : [];

  const handleSubmit = () => {
    if (state && lga) {
      router.push(`/representatives?state=${encodeURIComponent(state)}&lga=${encodeURIComponent(lga)}`);
    }
  };

  const handleGeolocate = async () => {
    setIsLocating(true);
    try {
      const position = await new Promise<GeolocationPosition>((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(resolve, reject);
      });
      
      // Call API to reverse geocode
      const response = await fetch(
        `/api/geocode?lat=${position.coords.latitude}&lng=${position.coords.longitude}`
      );
      const data = await response.json();
      
      if (data.state && data.lga) {
        setState(data.state);
        setLga(data.lga);
      }
    } catch (error) {
      console.error("Geolocation error:", error);
    } finally {
      setIsLocating(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <Select value={state} onValueChange={(value) => { setState(value); setLga(""); }}>
          <SelectTrigger>
            <SelectValue placeholder="Select State" />
          </SelectTrigger>
          <SelectContent>
            {STATES.map((s) => (
              <SelectItem key={s} value={s}>
                {s}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={lga} onValueChange={setLga} disabled={!state}>
          <SelectTrigger>
            <SelectValue placeholder="Select LGA" />
          </SelectTrigger>
          <SelectContent>
            {availableLgas.map((l) => (
              <SelectItem key={l} value={l}>
                {l}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Button
        className="w-full bg-green-600 hover:bg-green-700"
        disabled={!state || !lga}
        onClick={handleSubmit}
      >
        Find My Representatives
      </Button>

      <Button
        variant="outline"
        className="w-full"
        onClick={handleGeolocate}
        disabled={isLocating}
      >
        {isLocating ? (
          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
        ) : (
          <MapPin className="h-4 w-4 mr-2" />
        )}
        Use My Current Location
      </Button>
    </div>
  );
}
```

### 5. Politician Card (components/politicians/politician-card.tsx)

```tsx
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

interface PoliticianCardProps {
  id: string;
  name: string;
  position: string;
  party: string;
  state: string;
  imageUrl?: string;
  promiseScore?: number;
}

const partyColors: Record<string, string> = {
  APC: "bg-blue-900 text-white",
  PDP: "bg-red-600 text-white",
  LP: "bg-green-600 text-white",
  NNPP: "bg-purple-600 text-white",
};

export function PoliticianCard({
  id,
  name,
  position,
  party,
  state,
  imageUrl,
  promiseScore,
}: PoliticianCardProps) {
  const initials = name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2);

  return (
    <Link href={`/politicians/${id}`}>
      <Card className="hover:shadow-lg transition-shadow cursor-pointer">
        <CardContent className="p-6 text-center">
          <Avatar className="w-20 h-20 mx-auto mb-4">
            <AvatarImage src={imageUrl} alt={name} />
            <AvatarFallback className="text-lg bg-gray-200">{initials}</AvatarFallback>
          </Avatar>
          
          <h3 className="font-semibold text-gray-900 mb-1">{name}</h3>
          
          <Badge className={partyColors[party] || "bg-gray-500"}>{party}</Badge>
          
          <p className="text-sm text-gray-600 mt-2">{position}</p>
          <p className="text-xs text-gray-500">{state}</p>
          
          {promiseScore !== undefined && (
            <div className="mt-4">
              <div className="text-xs text-gray-500 mb-1">Promise Score</div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-green-600 h-2 rounded-full"
                  style={{ width: `${promiseScore}%` }}
                />
              </div>
              <div className="text-xs text-gray-600 mt-1">{promiseScore}%</div>
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
```

### 6. Issue Card (components/issues/issue-card.tsx)

```tsx
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { MapPin, Clock, FileText, Calendar } from "lucide-react";

interface IssueCardProps {
  id: string;
  title: string;
  domain: string;
  severity: "low" | "moderate" | "severe";
  location: string;
  updatedAt: string;
  eventCount: number;
  evidenceCount: number;
}

const severityColors = {
  severe: "bg-red-100 text-red-800 border-red-200",
  moderate: "bg-yellow-100 text-yellow-800 border-yellow-200",
  low: "bg-green-100 text-green-800 border-green-200",
};

const severityLabels = {
  severe: "🔴 Severe",
  moderate: "🟡 Moderate",
  low: "🟢 Low",
};

export function IssueCard({
  id,
  title,
  domain,
  severity,
  location,
  updatedAt,
  eventCount,
  evidenceCount,
}: IssueCardProps) {
  return (
    <Link href={`/issues/${id}`}>
      <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
        <CardContent className="p-6">
          <div className="flex items-center justify-between mb-3">
            <Badge variant="outline" className={severityColors[severity]}>
              {severityLabels[severity]}
            </Badge>
            <Badge variant="secondary">{domain}</Badge>
          </div>
          
          <h3 className="font-semibold text-gray-900 mb-3">{title}</h3>
          
          <div className="space-y-2 text-sm text-gray-600">
            <div className="flex items-center">
              <MapPin className="h-4 w-4 mr-2" />
              {location}
            </div>
            <div className="flex items-center">
              <Clock className="h-4 w-4 mr-2" />
              Updated {updatedAt}
            </div>
          </div>
          
          <div className="flex items-center justify-between mt-4 pt-4 border-t text-xs text-gray-500">
            <span className="flex items-center">
              <Calendar className="h-3 w-3 mr-1" />
              {eventCount} events
            </span>
            <span className="flex items-center">
              <FileText className="h-3 w-3 mr-1" />
              {evidenceCount} artifacts
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
```

### 7. Stats Counter (components/shared/stats-counter.tsx)

```tsx
"use client";

import { useEffect, useState } from "react";

interface StatsCounterProps {
  value: number;
  label: string;
  icon: React.ReactNode;
}

export function StatsCounter({ value, label, icon }: StatsCounterProps) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    const duration = 1000;
    const steps = 30;
    const stepValue = value / steps;
    let current = 0;

    const timer = setInterval(() => {
      current += stepValue;
      if (current >= value) {
        setCount(value);
        clearInterval(timer);
      } else {
        setCount(Math.floor(current));
      }
    }, duration / steps);

    return () => clearInterval(timer);
  }, [value]);

  return (
    <div className="flex flex-col items-center">
      <div className="text-green-600 mb-2">{icon}</div>
      <div className="text-3xl font-bold text-gray-900">{count.toLocaleString()}</div>
      <div className="text-sm text-gray-600">{label}</div>
    </div>
  );
}
```

### 8. Representatives Page (app/representatives/page.tsx)

```tsx
"use client";

import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { LocationPicker } from "@/components/representatives/location-picker";
import { useRepresentatives } from "@/hooks/use-representatives";
import { MapPin, Building2, Landmark, Home, ExternalLink, MessageCircle } from "lucide-react";
import Link from "next/link";

export default function RepresentativesPage() {
  const searchParams = useSearchParams();
  const state = searchParams.get("state");
  const lga = searchParams.get("lga");

  const { data: reps, isLoading } = useRepresentatives(state, lga);

  return (
    <div className="container py-8">
      <h1 className="text-3xl font-bold mb-2">Find Your Representatives</h1>
      <p className="text-gray-600 mb-8">
        Enter your location to see who represents you at every level
      </p>

      <Card className="mb-8">
        <CardContent className="p-6">
          <LocationPicker />
        </CardContent>
      </Card>

      {state && lga && (
        <>
          <div className="flex items-center mb-6 text-sm text-gray-600">
            <MapPin className="h-4 w-4 mr-2" />
            Showing representatives for <strong className="mx-1">{lga}, {state}</strong>
          </div>

          {isLoading ? (
            <div>Loading...</div>
          ) : (
            <div className="space-y-8">
              {/* Federal Level */}
              <section>
                <h2 className="text-xl font-bold flex items-center mb-4">
                  <Landmark className="h-5 w-5 mr-2" />
                  Federal Level
                </h2>
                <div className="space-y-4">
                  {reps?.federal?.map((rep) => (
                    <RepCard key={rep.id} rep={rep} />
                  ))}
                </div>
              </section>

              {/* State Level */}
              <section>
                <h2 className="text-xl font-bold flex items-center mb-4">
                  <Building2 className="h-5 w-5 mr-2" />
                  State Level
                </h2>
                <div className="space-y-4">
                  {reps?.state?.map((rep) => (
                    <RepCard key={rep.id} rep={rep} />
                  ))}
                </div>
              </section>

              {/* Local Level */}
              <section>
                <h2 className="text-xl font-bold flex items-center mb-4">
                  <Home className="h-5 w-5 mr-2" />
                  Local Level
                </h2>
                <div className="space-y-4">
                  {reps?.local?.map((rep) => (
                    <RepCard key={rep.id} rep={rep} />
                  ))}
                </div>
              </section>
            </div>
          )}

          {/* Report Issue CTA */}
          <Card className="mt-8 bg-gray-50">
            <CardContent className="p-6 text-center">
              <h3 className="font-semibold mb-2">Report an Issue in {lga}</h3>
              <p className="text-sm text-gray-600 mb-4">
                See a problem? Let us know. We'll track it and connect it to the responsible representatives.
              </p>
              <Button className="bg-green-600 hover:bg-green-700">
                <MessageCircle className="h-4 w-4 mr-2" />
                Report via WhatsApp
              </Button>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function RepCard({ rep }: { rep: any }) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-start gap-4">
          <Avatar className="w-16 h-16">
            <AvatarImage src={rep.imageUrl} alt={rep.name} />
            <AvatarFallback>{rep.name.slice(0, 2)}</AvatarFallback>
          </Avatar>
          
          <div className="flex-1">
            <div className="text-sm text-gray-500 mb-1">{rep.position}</div>
            <h3 className="font-semibold text-lg">{rep.name}</h3>
            <Badge className="mt-1">{rep.party}</Badge>
            
            {rep.promiseScore !== undefined && (
              <div className="mt-3">
                <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                  <span>Promise Score</span>
                  <span>{rep.promiseScore}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-green-600 h-2 rounded-full"
                    style={{ width: `${rep.promiseScore}%` }}
                  />
                </div>
              </div>
            )}
          </div>
          
          <Link href={`/politicians/${rep.id}`}>
            <Button variant="outline" size="sm">
              View Profile
              <ExternalLink className="h-3 w-3 ml-2" />
            </Button>
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
```

### 9. Constants (lib/constants.ts)

```typescript
export const STATES = [
  "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue", 
  "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu", 
  "FCT", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", 
  "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", 
  "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara"
];

export const LGAS: Record<string, string[]> = {
  "Lagos": [
    "Agege", "Ajeromi-Ifelodun", "Alimosho", "Amuwo-Odofin", "Apapa",
    "Badagry", "Epe", "Eti-Osa", "Ibeju-Lekki", "Ifako-Ijaiye",
    "Ikeja", "Ikorodu", "Kosofe", "Lagos Island", "Lagos Mainland",
    "Mushin", "Ojo", "Oshodi-Isolo", "Shomolu", "Surulere"
  ],
  "Ogun": [
    "Abeokuta North", "Abeokuta South", "Ado-Odo/Ota", "Ewekoro",
    "Ifo", "Ijebu East", "Ijebu North", "Ijebu North East", "Ijebu Ode",
    "Ikenne", "Imeko Afon", "Ipokia", "Obafemi Owode", "Odeda",
    "Odogbolu", "Ogun Waterside", "Remo North", "Sagamu", "Yewa North", "Yewa South"
  ],
  // Add more states...
};

export const PARTY_COLORS: Record<string, string> = {
  "APC": "#1e3a8a",
  "PDP": "#dc2626",
  "LP": "#16a34a",
  "NNPP": "#7c3aed",
  "APGA": "#eab308",
};
```

### 10. API Client (lib/api.ts)

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = {
  politicians: {
    list: async (params?: Record<string, string>) => {
      const query = params ? `?${new URLSearchParams(params)}` : "";
      const res = await fetch(`${API_BASE}/api/politicians${query}`);
      return res.json();
    },
    get: async (id: string) => {
      const res = await fetch(`${API_BASE}/api/politicians/${id}`);
      return res.json();
    },
    search: async (query: string) => {
      const res = await fetch(`${API_BASE}/api/politicians/search?q=${query}`);
      return res.json();
    },
  },

  representatives: {
    byLocation: async (state: string, lga: string) => {
      const res = await fetch(
        `${API_BASE}/api/representatives?state=${encodeURIComponent(state)}&lga=${encodeURIComponent(lga)}`
      );
      return res.json();
    },
  },

  issues: {
    list: async (params?: Record<string, string>) => {
      const query = params ? `?${new URLSearchParams(params)}` : "";
      const res = await fetch(`${API_BASE}/api/issues${query}`);
      return res.json();
    },
    get: async (id: string) => {
      const res = await fetch(`${API_BASE}/api/issues/${id}`);
      return res.json();
    },
  },

  stats: {
    overview: async () => {
      const res = await fetch(`${API_BASE}/api/stats`);
      return res.json();
    },
  },
};
```

### 11. Hooks (hooks/use-representatives.ts)

```typescript
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useRepresentatives(state: string | null, lga: string | null) {
  return useQuery({
    queryKey: ["representatives", state, lga],
    queryFn: () => api.representatives.byLocation(state!, lga!),
    enabled: !!state && !!lga,
  });
}

export function usePoliticians(params?: Record<string, string>) {
  return useQuery({
    queryKey: ["politicians", params],
    queryFn: () => api.politicians.list(params),
  });
}

export function usePolitician(id: string) {
  return useQuery({
    queryKey: ["politician", id],
    queryFn: () => api.politicians.get(id),
    enabled: !!id,
  });
}
```

### 12. Footer (components/layout/footer.tsx)

```tsx
import Link from "next/link";

export function Footer() {
  return (
    <footer className="bg-gray-900 text-gray-300 py-12">
      <div className="container">
        <div className="grid md:grid-cols-4 gap-8">
          <div>
            <div className="flex items-center space-x-2 mb-4">
              <span className="text-2xl">🇳🇬</span>
              <span className="font-bold text-xl text-white">Decide9ja</span>
            </div>
            <p className="text-sm">
              Nigeria's civic information platform. Know your representatives, hold them accountable.
            </p>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-4">Explore</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/politicians" className="hover:text-white">Politicians</Link></li>
              <li><Link href="/issues" className="hover:text-white">Issues</Link></li>
              <li><Link href="/representatives" className="hover:text-white">Find My Reps</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-4">About</h4>
            <ul className="space-y-2 text-sm">
              <li><Link href="/about" className="hover:text-white">About Us</Link></li>
              <li><Link href="/contact" className="hover:text-white">Contact</Link></li>
              <li><Link href="/privacy" className="hover:text-white">Privacy Policy</Link></li>
            </ul>
          </div>

          <div>
            <h4 className="font-semibold text-white mb-4">Connect</h4>
            <ul className="space-y-2 text-sm">
              <li><a href="#" className="hover:text-white">WhatsApp</a></li>
              <li><a href="#" className="hover:text-white">Twitter/X</a></li>
              <li><a href="#" className="hover:text-white">Instagram</a></li>
            </ul>
          </div>
        </div>

        <div className="border-t border-gray-800 mt-8 pt-8 text-sm text-center">
          © {new Date().getFullYear()} Decide9ja. Built for Nigerians. 🇳🇬
        </div>
      </div>
    </footer>
  );
}
```

---

## Environment Variables

Create `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WHATSAPP_NUMBER=+14155238886
```

---

## Run the Project

```bash
npm run dev
```

Open http://localhost:3000

---

## Deployment

```bash
# Deploy to Vercel
vercel

# Or build for production
npm run build
npm start
```

---

## Backend API Endpoints Required

Your FastAPI backend needs these endpoints:

```
GET  /api/politicians              # List with filters
GET  /api/politicians/{id}         # Single politician
GET  /api/politicians/search       # Search
GET  /api/representatives          # By state/lga
GET  /api/issues                   # List issues
GET  /api/issues/{id}              # Single issue
GET  /api/stats                    # Overview stats
```

---

## Next Steps After MVP

1. Add politician profile page with full details
2. Add issues explorer with Nigeria map
3. Add admin dashboard
4. Add authentication
5. Add issue reporting form
6. Add search functionality
7. Add dark mode
8. Add PWA support
