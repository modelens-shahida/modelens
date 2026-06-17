'use client';

import React, { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { Search, Sparkles, Database, Image as ImageIcon, Loader2, ArrowLeft, Layers } from 'lucide-react';
import Link from 'next/link';

export default function SearchPage() {
  const [brands, setBrands] = useState<any[]>([]);
  const [selectedBrandId, setSelectedBrandId] = useState<string>('');
  const [query, setQuery] = useState<string>('');
  const [searchType, setSearchType] = useState<string>('hybrid');
  const [results, setResults] = useState<any[] | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingBrands, setLoadingBrands] = useState<boolean>(true);

  // Load brands on mount
  useEffect(() => {
    async function loadBrands() {
      try {
        const data = await api.get('/api/v1/brands');
        setBrands(data);
        if (data.length > 0) {
          setSelectedBrandId(data[0].id.toString());
        }
      } catch (err) {
        console.error('Failed to load brands:', err);
      } finally {
        setLoadingBrands(false);
      }
    }
    loadBrands();
  }, []);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim() || !selectedBrandId) return;

    setLoading(true);
    setResults(null);
    try {
      const endpoint = `/api/v1/search?brand_id=${selectedBrandId}&q=${encodeURIComponent(query.trim())}&type=${searchType}&limit=24`;
      const data = await api.get(endpoint);
      setResults(data);
    } catch (err: any) {
      console.error(err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans p-6 md:p-12 selection:bg-purple-900 selection:text-white">
      <div className="max-w-6xl mx-auto space-y-8">
        
        {/* Navigation / Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-zinc-900 pb-6">
          <div className="space-y-1">
            <Link 
              href="/dashboard" 
              className="inline-flex items-center gap-1.5 text-[10px] font-bold text-zinc-500 hover:text-purple-400 uppercase tracking-widest transition-all mb-2"
            >
              <ArrowLeft size={10} /> Back to Dashboard
            </Link>
            <h1 className="text-xl md:text-2xl font-bold tracking-wide text-zinc-100 flex items-center gap-2.5">
              <Search className="text-purple-400" size={24} />
              Unified Asset Search
            </h1>
            <p className="text-xs text-zinc-400">
              Query fashion catalog assets using Full-Text, Semantic Vector, or Hybrid Search
            </p>
          </div>
        </div>

        {/* Configuration Desk */}
        <div className="bg-zinc-900/30 border border-zinc-900 rounded-2xl p-5 md:p-6 shadow-xl space-y-5">
          <form onSubmit={handleSearch} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
              
              {/* Pick Brand Workspace */}
              <div className="md:col-span-4 space-y-1.5">
                <label className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">
                  Brand Workspace
                </label>
                {loadingBrands ? (
                  <div className="flex items-center gap-2 h-10 px-3 border border-zinc-900 rounded-xl bg-zinc-950 text-zinc-500 text-xs">
                    <Loader2 className="animate-spin text-purple-500" size={12} />
                    Loading workspaces...
                  </div>
                ) : (
                  <select
                    value={selectedBrandId}
                    onChange={(e) => setSelectedBrandId(e.target.value)}
                    className="w-full h-10 bg-zinc-950 border border-zinc-850 hover:border-zinc-800 focus:border-purple-500 rounded-xl px-3 text-xs text-zinc-100 outline-none cursor-pointer transition-all"
                  >
                    {brands.map((b) => (
                      <option key={b.id} value={b.id}>{b.name}</option>
                    ))}
                  </select>
                )}
              </div>

              {/* Pick Search Type */}
              <div className="md:col-span-4 space-y-1.5">
                <label className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">
                  Search Engine Type
                </label>
                <select
                  value={searchType}
                  onChange={(e) => setSearchType(e.target.value)}
                  className="w-full h-10 bg-zinc-950 border border-zinc-850 hover:border-zinc-800 focus:border-purple-500 rounded-xl px-3 text-xs text-zinc-100 outline-none cursor-pointer transition-all"
                >
                  <option value="hybrid">Hybrid Search (RRF Rank)</option>
                  <option value="vector">Semantic Vector (pgvector)</option>
                  <option value="fts">Full-Text Search (FTS)</option>
                </select>
              </div>

              {/* Search Bar Input */}
              <div className="md:col-span-4 space-y-1.5 flex flex-col justify-end">
                <span className="hidden md:block text-[10px] font-bold text-transparent select-none">Action</span>
                <button
                  type="submit"
                  disabled={loading || !query.trim() || !selectedBrandId}
                  className="w-full h-10 bg-purple-600 hover:bg-purple-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-white text-xs font-semibold px-4 rounded-xl flex items-center justify-center gap-2 transition-all cursor-pointer shadow-lg shadow-purple-950/20 disabled:shadow-none"
                >
                  {loading ? (
                    <Loader2 className="animate-spin" size={14} />
                  ) : (
                    <Search size={14} />
                  )}
                  Search Database
                </button>
              </div>
            </div>

            {/* Query Input String */}
            <div className="space-y-1.5">
              <label className="text-[10px] font-bold text-zinc-400 uppercase tracking-wider block">
                Search Query
              </label>
              <div className="relative">
                <input
                  type="text"
                  required
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="e.g. leather bags, golden hour portraits, summer accessories..."
                  className="w-full bg-zinc-950 border border-zinc-850 focus:border-purple-500 rounded-xl pl-4 pr-12 py-3 text-xs text-zinc-100 outline-none transition-all placeholder:text-zinc-600"
                />
                <div className="absolute right-4 top-3.5 flex items-center gap-1.5 pointer-events-none text-zinc-600">
                  {searchType === 'hybrid' && <Sparkles size={13} className="text-purple-400/80" />}
                  {searchType === 'vector' && <Layers size={13} className="text-indigo-400/80" />}
                  {searchType === 'fts' && <Database size={13} className="text-emerald-400/80" />}
                </div>
              </div>
            </div>
          </form>
        </div>

        {/* Results Workspace */}
        <div className="space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-widest text-zinc-500">
            Search Results {results !== null && `(${results.length})`}
          </h2>

          {loading ? (
            <div className="flex flex-col items-center justify-center py-24 gap-3 bg-zinc-900/10 border border-zinc-900 rounded-2xl">
              <Loader2 className="animate-spin text-purple-500" size={28} />
              <span className="text-zinc-500 text-xs tracking-wider animate-pulse">Running semantic query match...</span>
            </div>
          ) : results === null ? (
            <div className="text-center py-20 bg-zinc-900/10 border border-dashed border-zinc-900 rounded-2xl text-zinc-500 text-xs flex flex-col items-center justify-center gap-3">
              <Search size={32} className="text-zinc-800" />
              Enter query text above to search catalog assets.
            </div>
          ) : results.length === 0 ? (
            <div className="text-center py-20 bg-zinc-900/10 border border-zinc-900 rounded-2xl text-zinc-500 text-xs">
              No assets found matching the query in this brand workspace.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
              {results.map((asset) => {
                // Determine search badge styling
                let badgeStyle = "text-purple-400 bg-purple-950/40 border-purple-800/30";
                let typeLabel = "Hybrid";
                if (asset.search_type === "fts") {
                  badgeStyle = "text-emerald-400 bg-emerald-950/40 border-emerald-800/30";
                  typeLabel = "Full-Text";
                } else if (asset.search_type === "vector") {
                  badgeStyle = "text-indigo-400 bg-indigo-950/40 border-indigo-800/30";
                  typeLabel = "Vector similarity";
                }

                // Parse display score
                const matchScore = asset.score ? Math.round(asset.score * 100) : null;

                return (
                  <div
                    key={asset.id}
                    className="bg-zinc-900/20 border border-zinc-850 hover:border-zinc-800 hover:bg-zinc-900/35 p-4 rounded-2xl transition-all flex flex-col justify-between gap-4 group relative overflow-hidden"
                  >
                    {/* Visual Preview */}
                    <div className="relative aspect-video rounded-xl bg-zinc-950 border border-zinc-900 flex items-center justify-center overflow-hidden shrink-0">
                      {asset.storage_path ? (
                        <img
                          src={asset.storage_path}
                          alt={asset.name || asset.filename}
                          className="w-full h-full object-cover group-hover:scale-105 transition-all duration-300"
                          onError={(e) => {
                            // Fallback to placeholder icon on load error
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                      ) : (
                        <ImageIcon size={28} className="text-zinc-800" />
                      )}
                    </div>

                    {/* Metadata Content */}
                    <div className="space-y-3 text-left">
                      <div className="space-y-1">
                        <div className="flex justify-between items-start gap-2">
                          <h3 className="text-xs font-bold text-zinc-200 group-hover:text-white truncate flex-1">
                            {asset.name || asset.filename}
                          </h3>
                          <span className={`text-[8px] font-bold border px-2 py-0.5 rounded-full uppercase tracking-wider shrink-0 ${badgeStyle}`}>
                            {typeLabel}
                          </span>
                        </div>
                        <p className="text-[10px] text-zinc-500 truncate font-mono">
                          {asset.filename}
                        </p>
                      </div>

                      {/* Score Indicator */}
                      {matchScore !== null && matchScore > 0 && (
                        <div className="space-y-1">
                          <div className="flex justify-between items-center text-[9px]">
                            <span className="text-zinc-500">Search Match Score</span>
                            <span className="text-purple-400 font-bold">{matchScore}%</span>
                          </div>
                          <div className="w-full bg-zinc-950 h-1.5 rounded-full overflow-hidden border border-zinc-900/50">
                            <div 
                              className="bg-purple-500 h-full rounded-full" 
                              style={{ width: `${Math.min(matchScore, 100)}%` }}
                            />
                          </div>
                        </div>
                      )}

                      {/* Display metadata tags if any */}
                      {asset.metadata && Object.keys(asset.metadata).length > 0 && (
                        <div className="flex flex-wrap gap-1 pt-1.5 border-t border-zinc-900">
                          {Object.entries(asset.metadata).map(([key, val]: any) => {
                            if (typeof val === 'string' && val) {
                              return (
                                <span key={key} className="text-[8px] bg-zinc-900 border border-zinc-850 px-1.5 py-0.5 rounded text-zinc-400">
                                  {val}
                                </span>
                              );
                            }
                            return null;
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

