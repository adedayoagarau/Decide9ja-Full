export default function AboutPage() {
    return (
        <div className="container py-12 max-w-3xl">
            <h1 className="text-3xl font-bold mb-6">About Decide9ja</h1>

            <div className="prose prose-lg max-w-none">
                <p className="text-xl text-muted-foreground mb-8">
                    Decide9ja is Nigeria&apos;s civic information platform, helping citizens know their representatives and hold them accountable.
                </p>

                <h2 className="text-2xl font-semibold mt-8 mb-4">Our Mission</h2>
                <p className="text-muted-foreground">
                    We believe that an informed citizenry is the foundation of good governance. Decide9ja provides easy access to information about Nigerian politicians at every level — from your LGA chairman to the President.
                </p>

                <h2 className="text-2xl font-semibold mt-8 mb-4">What We Do</h2>
                <ul className="space-y-2 text-muted-foreground">
                    <li>📍 <strong>Find Your Representatives</strong> — Enter your location to see who represents you at federal, state, and local levels.</li>
                    <li>👤 <strong>Politician Profiles</strong> — View comprehensive profiles including biography, party affiliation, and promises.</li>
                    <li>✅ <strong>Promise Tracking</strong> — We track campaign promises and report on their status: kept, in progress, or broken.</li>
                    <li>📝 <strong>Issue Reporting</strong> — Report community issues that need attention from your representatives.</li>
                    <li>💬 <strong>WhatsApp Access</strong> — Get all this information via WhatsApp — no app download needed.</li>
                </ul>

                <h2 className="text-2xl font-semibold mt-8 mb-4">Our Data</h2>
                <p className="text-muted-foreground">
                    We track <strong>505+ politicians</strong> across Nigeria, including:
                </p>
                <ul className="space-y-1 text-muted-foreground">
                    <li>• The President and Vice President</li>
                    <li>• All 109 Senators</li>
                    <li>• All 360 House of Representatives members</li>
                    <li>• All 36 State Governors</li>
                    <li>• State House of Assembly members</li>
                    <li>• LGA Chairmen</li>
                </ul>

                <h2 className="text-2xl font-semibold mt-8 mb-4">Contact Us</h2>
                <p className="text-muted-foreground">
                    Have feedback or want to contribute? Reach out via{" "}
                    <a href="https://wa.me/2348160179151" className="text-primary hover:underline">
                        WhatsApp
                    </a>.
                </p>
            </div>
        </div>
    );
}
