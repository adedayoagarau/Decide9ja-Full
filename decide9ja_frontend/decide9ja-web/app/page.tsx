import { Hero } from "@/components/landing/hero";
import { ProofStrip } from "@/components/landing/proof-strip";
import { HowItWorks } from "@/components/landing/how-it-works";
import { FeaturesGrid } from "@/components/landing/features-grid";
import { LiveDemo } from "@/components/landing/live-demo";
import { CoverageMap } from "@/components/landing/coverage-map";
import { TrustSection } from "@/components/landing/trust-section";
import { Partners } from "@/components/landing/partners";
import { FAQ } from "@/components/landing/faq";
import { MobileCTA } from "@/components/landing/mobile-cta";

export default function HomePage() {
  return (
    <>
      {/* Hero Section */}
      <Hero />

      {/* Proof Strip - Stats */}
      <ProofStrip />

      {/* How It Works - 3 Steps */}
      <HowItWorks />

      {/* Features Grid - What you can do */}
      <FeaturesGrid />

      {/* Live Demo - Chat transcript carousel */}
      <LiveDemo />

      {/* Coverage Map */}
      <CoverageMap />

      {/* Trust, Neutrality, Privacy */}
      <TrustSection />

      {/* Partners */}
      <Partners />

      {/* FAQ */}
      <FAQ />

      {/* Mobile Sticky CTA */}
      <MobileCTA />

      {/* Bottom padding for mobile CTA */}
      <div className="h-20 md:hidden" />
    </>
  );
}
