import Header from "@/components/Header";

export default function AboutPage() {
  return (
    <div className="min-h-screen bg-c-beige">
      <Header />

      <div className="max-w-3xl mx-auto px-4 md:px-8 py-12">
        <h1 className="text-3xl md:text-4xl font-bold mb-6">About Decide9ja</h1>

        <div className="space-y-6 text-base leading-relaxed text-gray-700">
          <p>
            Decide9ja is an AI-powered civic intelligence platform that helps Nigerians
            track their government's performance, understand political issues, and hold
            their representatives accountable.
          </p>

          <div className="bg-white border border-gray-200 p-6">
            <h2 className="font-bold text-lg mb-3 text-c-black">What We Track</h2>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
              <div className="border border-gray-200 p-3">
                <span className="text-lg block mb-1">{"\u26A1"}</span>
                <span className="font-bold">Power</span>
                <p className="text-gray-500 text-xs mt-1">Electricity, grid failures, generation</p>
              </div>
              <div className="border border-gray-200 p-3">
                <span className="text-lg block mb-1">{"\uD83D\uDEE3\uFE0F"}</span>
                <span className="font-bold">Roads</span>
                <p className="text-gray-500 text-xs mt-1">Infrastructure, contracts, maintenance</p>
              </div>
              <div className="border border-gray-200 p-3">
                <span className="text-lg block mb-1">{"\uD83D\uDEE1\uFE0F"}</span>
                <span className="font-bold">Security</span>
                <p className="text-gray-500 text-xs mt-1">Safety, policing, defense spending</p>
              </div>
              <div className="border border-gray-200 p-3">
                <span className="text-lg block mb-1">{"\uD83D\uDCA7"}</span>
                <span className="font-bold">Water</span>
                <p className="text-gray-500 text-xs mt-1">Clean water access, sanitation</p>
              </div>
              <div className="border border-gray-200 p-3">
                <span className="text-lg block mb-1">{"\uD83C\uDFE5"}</span>
                <span className="font-bold">Health</span>
                <p className="text-gray-500 text-xs mt-1">Healthcare, hospitals, budgets</p>
              </div>
              <div className="border border-gray-200 p-3">
                <span className="text-lg block mb-1">{"\uD83C\uDF93"}</span>
                <span className="font-bold">Education</span>
                <p className="text-gray-500 text-xs mt-1">Schools, ASUU, funding</p>
              </div>
            </div>
          </div>

          <div className="bg-white border border-gray-200 p-6">
            <h2 className="font-bold text-lg mb-3 text-c-black">How It Works</h2>
            <p>
              Our AI systems continuously monitor news sources, government publications,
              budget documents, and legislative proceedings. We use natural language processing
              and machine learning to extract key information, detect anomalies, and present
              findings in an accessible format.
            </p>
            <p className="mt-3">
              You can interact with Decide9ja through this website, or via WhatsApp by chatting
              with Tade, our AI political analyst.
            </p>
          </div>

          <div className="bg-white border border-gray-200 p-6">
            <h2 className="font-bold text-lg mb-3 text-c-black">Data Sources</h2>
            <p className="text-sm text-gray-600">
              Nigerian news outlets, Budget Office publications, National Assembly records,
              INEC data, state government gazettes, and citizen reports via WhatsApp.
              All data is verified through multiple sources where possible.
            </p>
          </div>

          <div className="bg-c-black text-white p-6">
            <h2 className="font-bold text-lg mb-3">Disclaimer</h2>
            <p className="text-gray-300 text-sm">
              Decide9ja uses AI to analyze publicly available data. While we strive for accuracy,
              AI analysis may contain errors. Always verify critical information from official sources.
              This platform is for informational purposes and civic engagement.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
