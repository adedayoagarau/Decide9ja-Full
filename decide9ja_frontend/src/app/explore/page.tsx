"use client";

import { useState, useEffect } from "react";
import Header from "@/components/Header";
import ChatWidget from "@/components/ChatWidget";
import LoadingState from "@/components/LoadingState";
import { getTrendingSearches, advancedSearch, getExploreTopics } from "@/lib/api";

export default function ExplorePage() {
  const [query, setQuery] = useState("");
  const [trending, setTrending] = useState<any[]>([]);
  const [topics, setTopics] = useState<any[]>([]);
  const [results, setResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.allSettled([
      getTrendingSearches(15),
      getExploreTopics(),
    ]).then(([trendRes, topicRes]) => {
      if (trendRes.status === "fulfilled") setTrending(trendRes.value.queries || trendRes.value.trending || []);
      if (topicRes.status === "fulfilled") setTopics(topicRes.value.topics || []);
      setLoading(false);
    });
  }, []);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const data = await advancedSearch({ query, limit: 20 });
      setResults(data.results || []);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="min-h-screen bg-c-beige">
      <Header />

      <div className="px-4 md:px-8 py-8 max-w-5xl mx-auto">
        <h1 className="text-2xl md:text-3xl font-bold mb-2">Explore</h1>
        <p className="text-sm text-gray-500 font-mono mb-8">Search across politicians, issues, news, and bills</p>

        {/* Search bar */}
        <div className="flex mb-8">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            placeholder="Search for politicians, issues, topics..."
            className="flex-1 border border-gray-300 px-4 py-3 text-sm outline-none bg-white focus:border-c-green"
          />
          <button
            onClick={handleSearch}
            disabled={searching}
            className="bg-c-green text-white px-6 font-mono text-sm uppercase hover:brightness-110 disabled:opacity-50"
          >
            {searching ? "..." : "Search"}
          </button>
        </div>

        {/* Search results */}
        {results.length > 0 && (
          <div className="mb-8">
            <h2 className="text-sm font-mono text-gray-400 uppercase mb-4">Results ({results.length})</h2>
            <div className="space-y-3">
              {results.map((r: any, i: number) => (
                <div key={i} className="bg-white border border-gray-200 p-4 hover:border-gray-400 transition-colors">
                  <h3 className="font-bold text-sm mb-1">{r.title || r.name || "Result"}</h3>
                  <p className="text-sm text-gray-600">{r.summary || r.excerpt || r.description || ""}</p>
                  {r.type && <span className="text-[10px] font-mono text-gray-400 mt-2 inline-block">{r.type}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Trending searches */}
        {!results.length && !searching && (
          <>
            {loading ? (
              <LoadingState message="Loading trends..." />
            ) : (
              <>
                {trending.length > 0 && (
                  <div className="mb-8">
                    <h2 className="text-sm font-mono text-gray-400 uppercase mb-4">Trending Searches</h2>
                    <div className="flex flex-wrap gap-2">
                      {trending.map((t: any, i: number) => (
                        <button
                          key={i}
                          onClick={() => { setQuery(t.query || t); handleSearch(); }}
                          className="bg-white border border-gray-200 px-3 py-2 text-sm hover:border-c-green hover:bg-c-green/5 transition-colors"
                        >
                          {t.query || t}
                          {t.count && <span className="text-[10px] font-mono text-gray-400 ml-2">{t.count}</span>}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {topics.length > 0 && (
                  <div>
                    <h2 className="text-sm font-mono text-gray-400 uppercase mb-4">Explore Topics</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {topics.map((topic: any, i: number) => (
                        <button
                          key={i}
                          onClick={() => { setQuery(topic.name || topic.topic || topic); handleSearch(); }}
                          className="bg-white border border-gray-200 p-4 text-left hover:border-c-green transition-colors"
                        >
                          <h3 className="font-bold text-sm mb-1">{topic.name || topic.topic || topic}</h3>
                          {topic.description && <p className="text-xs text-gray-500">{topic.description}</p>}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>

      <ChatWidget />
    </div>
  );
}
