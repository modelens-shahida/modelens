"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { 
  User, 
  ArrowLeft, 
  Lock, 
  ShieldCheck, 
  CheckCircle2, 
  Layers, 
  Dna, 
  Camera, 
  Award, 
  Sparkles, 
  Eye, 
  History, 
  Package, 
  Palette, 
  Shirt, 
  Footprints, 
  ShoppingBag, 
  Glasses, 
  Gem, 
  Loader2,
  ChevronRight,
  ExternalLink
} from "lucide-react";
import { MOCK_ELISKA_CHARACTER, CHARACTER_STATUS } from "@/lib/characterSchema";
import { characterRegistryApi } from "@/lib/characterRegistryApi";

const PRODUCT_TYPES = [
  { id: "garment", label: "Garments / Apparel", icon: Shirt },
  { id: "shoes", label: "Footwear / Shoes", icon: Footprints },
  { id: "bags", label: "Handbags & Totes", icon: ShoppingBag },
  { id: "eyewear", label: "Eyewear & Sunglasses", icon: Glasses },
  { id: "jewelry", label: "Jewelry & Accessories", icon: Gem },
];

export default function EliskaCharacterDetailPage() {
  const [activeTab, setActiveTab] = useState("overview"); 
  // overview | capabilities | poses | styling | identity | body | angles | versions

  // Dynamic API state
  const [loading, setLoading] = useState(true);
  const [versionData, setVersionData] = useState(null);
  const [capabilities, setCapabilities] = useState([]);
  const [stylingOptions, setStylingOptions] = useState({ hair_styles: [], makeup_styles: [], expressions: [] });
  const [selectedProductType, setSelectedProductType] = useState("garment");
  const [poses, setPoses] = useState([]);
  const [loadingPoses, setLoadingPoses] = useState(false);
  const [versionsList, setVersionsList] = useState([]);

  const characterId = "EE-F-002";

  // Initial data load
  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [verRes, capRes, styleRes, verListRes] = await Promise.allSettled([
          characterRegistryApi.getCurrentVersion(characterId),
          characterRegistryApi.getCapabilities(characterId),
          characterRegistryApi.getStylingOptions(characterId),
          characterRegistryApi.listVersions(characterId),
        ]);

        if (verRes.status === "fulfilled" && verRes.value) {
          setVersionData(verRes.value);
        }
        if (capRes.status === "fulfilled" && capRes.value) {
          setCapabilities(capRes.value.capabilities || capRes.value || []);
        }
        if (styleRes.status === "fulfilled" && styleRes.value) {
          setStylingOptions(styleRes.value);
        }
        if (verListRes.status === "fulfilled" && verListRes.value) {
          setVersionsList(verListRes.value.versions || verListRes.value || []);
        }
      } catch (err) {
        console.warn("Failed to load live character registry data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [characterId]);

  // Load poses when product type changes
  useEffect(() => {
    async function loadPoses() {
      try {
        setLoadingPoses(true);
        const res = await characterRegistryApi.getPoses(characterId, selectedProductType);
        if (res && res.poses) {
          setPoses(res.poses);
        } else if (Array.isArray(res)) {
          setPoses(res);
        } else {
          setPoses([]);
        }
      } catch (err) {
        console.warn("Using fallback poses for product type", selectedProductType, err);
        setPoses([]);
      } finally {
        setLoadingPoses(false);
      }
    }
    loadPoses();
  }, [characterId, selectedProductType]);

  const char = {
    ...MOCK_ELISKA_CHARACTER,
    version: versionData?.character_version || "1.0",
    status: versionData?.status || "PRODUCTION",
    is_locked_production: true,
    canonical_height_cm: versionData?.canonical_height_cm || 178,
    stature: versionData?.stature || "Tall",
    body_archetype: versionData?.body_archetype || "High-Fashion Runway Slim",
  };

  const tabs = [
    { id: "overview", label: "OVERVIEW", icon: User },
    { id: "capabilities", label: "CAPABILITY PACKS", icon: Package },
    { id: "poses", label: "POSES & FRAMING", icon: Camera },
    { id: "styling", label: "STYLING & APPEARANCE", icon: Sparkles },
    { id: "identity", label: "IDENTITY DNA", icon: Eye },
    { id: "body", label: "BODY ARCHITECTURE", icon: Dna },
    { id: "angles", label: "CANONICAL ANGLES", icon: Layers },
    { id: "versions", label: "VERSION REGISTRY", icon: History },
  ];

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 p-6 space-y-6">
      {/* Navigation Breadcrumb */}
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        <Link
          href="/dashboard/characters"
          className="flex items-center gap-2 text-xs font-semibold text-zinc-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Character Library (Casting Board)</span>
        </Link>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-cyan-400 font-bold">LOCKED IDENTITY DNA</span>
          <span className="text-xs text-zinc-600">•</span>
          <span className="text-xs font-mono text-zinc-400">{characterId}</span>
        </div>
      </div>

      {/* Header Row (Shahida Directive) */}
      <div className="max-w-6xl mx-auto bg-zinc-900/90 border border-zinc-800 rounded-2xl p-6 backdrop-blur-md shadow-xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-5">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-3xl font-extrabold text-white tracking-tight">{char.display_name}</h1>
              <span className="px-3 py-1 bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 text-xs font-mono font-bold rounded-full">
                {char.id}
              </span>
            </div>

            <div className="flex items-center gap-3 text-xs text-zinc-400 mt-2 font-mono">
              <span>Version {char.version}</span>
              <span>•</span>
              <span className="px-2.5 py-0.5 bg-indigo-500/10 border border-indigo-500/30 text-indigo-400 text-[10px] font-bold rounded-full flex items-center gap-1">
                <Lock className="w-3 h-3" />
                <span>IMMUTABLE IDENTITY</span>
              </span>
              <span className="px-2.5 py-0.5 bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold rounded-full flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" />
                <span>PRODUCTION CLEARED</span>
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/dashboard/create"
              className="bg-cyan-500 hover:bg-cyan-400 text-black font-bold text-xs px-5 py-2.5 rounded-xl transition-all shadow-lg shadow-cyan-500/20 flex items-center gap-2"
            >
              <Sparkles className="w-4 h-4" />
              <span>LAUNCH STUDIO SHOOT</span>
            </Link>
          </div>
        </div>

        {/* Hero Section & Details Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-6">
          {/* Large Hero Portrait (Shahida Directive) */}
          <div className="lg:col-span-4">
            <div className="bg-zinc-950 border border-zinc-800 rounded-2xl overflow-hidden shadow-2xl relative aspect-[3/4] flex items-center justify-center group">
              <div className="absolute inset-0 bg-gradient-to-t from-zinc-950 via-transparent to-transparent z-10 opacity-70" />
              <div className="text-center space-y-2 text-cyan-400/80 z-20">
                <User className="w-16 h-16 stroke-[1.2] mx-auto" />
                <span className="text-xs font-mono font-bold block text-white">HERO CANONICAL PORTRAIT</span>
                <span className="text-[10px] text-zinc-400 font-mono">ELISKA NOVAK • EE-F-002 V1.0</span>
              </div>
              <div className="absolute bottom-3 left-3 right-3 z-20 flex justify-between items-center text-[10px] font-mono text-zinc-400 bg-zinc-900/80 px-3 py-1.5 rounded-lg backdrop-blur-sm border border-zinc-800">
                <span>Height: {char.canonical_height_cm}cm</span>
                <span className="text-emerald-400 font-bold">100% LORAS LOCKED</span>
              </div>
            </div>
          </div>

          {/* Tabbed Content Area */}
          <div className="lg:col-span-8 flex flex-col justify-between">
            <div>
              {/* Tab Selector Bar */}
              <div className="flex items-center gap-1.5 border-b border-zinc-800 pb-3 overflow-x-auto scrollbar-thin scrollbar-thumb-zinc-800">
                {tabs.map((t) => {
                  const active = activeTab === t.id;
                  const Icon = t.icon;
                  return (
                    <button
                      key={t.id}
                      onClick={() => setActiveTab(t.id)}
                      className={`px-3 py-2 text-xs font-bold rounded-xl border transition-all flex items-center gap-1.5 whitespace-nowrap ${
                        active
                          ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/40 shadow-sm"
                          : "text-zinc-400 border-transparent hover:text-white hover:bg-zinc-800/50"
                      }`}
                    >
                      <Icon className="w-3.5 h-3.5" />
                      <span>{t.label}</span>
                    </button>
                  );
                })}
              </div>

              {/* Tab 1: OVERVIEW */}
              {activeTab === "overview" && (
                <div className="grid grid-cols-2 gap-4 mt-5">
                  <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl">
                    <span className="text-xs text-zinc-500 block">Height Anchor</span>
                    <p className="text-lg font-bold text-white mt-0.5">{char.canonical_height_cm} cm</p>
                    <span className="text-[10px] text-zinc-500 font-mono">Guaranteed Proportions</span>
                  </div>

                  <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl">
                    <span className="text-xs text-zinc-500 block">Stature Class</span>
                    <p className="text-lg font-bold text-white mt-0.5">{char.stature}</p>
                    <span className="text-[10px] text-zinc-500 font-mono">High-Fashion Standard</span>
                  </div>

                  <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl col-span-2">
                    <span className="text-xs text-zinc-500 block">Body Archetype</span>
                    <p className="text-base font-bold text-white mt-0.5">{char.body_archetype}</p>
                    <p className="text-xs text-zinc-400 mt-1">
                      Statuesque runway silhouette with natural clavicle and angular cheekbone landmarks.
                    </p>
                  </div>

                  <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl">
                    <span className="text-xs text-zinc-500 block">Identity Status</span>
                    <p className="text-sm font-bold text-indigo-400 mt-0.5 flex items-center gap-1.5">
                      <Lock className="w-3.5 h-3.5" />
                      <span>Locked (EE-F-002 V1.0)</span>
                    </p>
                  </div>

                  <div className="bg-zinc-950 border border-zinc-800/80 p-4 rounded-xl">
                    <span className="text-xs text-zinc-500 block">Production Eligibility</span>
                    <p className="text-sm font-bold text-emerald-400 mt-0.5 flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Production Active</span>
                    </p>
                  </div>
                </div>
              )}

              {/* Tab 2: CAPABILITY PACKS */}
              {activeTab === "capabilities" && (
                <div className="mt-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                        Versioned Capability Packs
                      </h3>
                      <p className="text-[11px] text-zinc-400">
                        Packs define model workflow routes, adapters, and preservation rules per SKU category.
                      </p>
                    </div>
                    <span className="text-[11px] font-mono text-cyan-400 font-semibold">
                      {capabilities.length > 0 ? `${capabilities.length} Packs Configured` : "Packs Active"}
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {[
                      { type: "GARMENT", label: "Garment / Apparel Pack", version: "V1.0", status: "PRODUCTION", desc: "Full drape preservation, texture rendering & collar structure." },
                      { type: "FOOTWEAR", label: "Footwear / Shoes Pack", version: "V1.0", status: "APPROVED", desc: "Ground contact posture, heel elevation & ankle geometry." },
                      { type: "BAGS", label: "Bags & Totes Pack", version: "V1.0", status: "APPROVED", desc: "Shoulder strap drape, arm tuck, and natural grip physics." },
                      { type: "EYEWEAR", label: "Eyewear Pack", version: "V1.0", status: "APPROVED", desc: "Nose bridge alignment, ear tuck, and glare suppression." },
                      { type: "JEWELRY", label: "Jewelry Pack", version: "V1.0", status: "VALIDATION", desc: "Macro close-up lighting, micro-reflection and skin contact." },
                      { type: "MOTION", label: "Motion & Dynamic Poses", version: "V1.0", status: "PRODUCTION", desc: "Editorial stride, runway walk, and fluid fabric dynamics." },
                    ].map((pack) => (
                      <div key={pack.type} className="bg-zinc-950 border border-zinc-800 p-3.5 rounded-xl space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="text-xs font-bold text-white font-mono">{pack.type}</span>
                          <span className={`px-2 py-0.5 text-[9px] font-bold rounded-full border ${
                            pack.status === "PRODUCTION" 
                              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                              : pack.status === "APPROVED"
                              ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/30"
                              : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                          }`}>
                            {pack.status}
                          </span>
                        </div>
                        <h4 className="text-xs font-semibold text-zinc-200">{pack.label}</h4>
                        <p className="text-[11px] text-zinc-400 leading-relaxed">{pack.desc}</p>
                        <div className="flex items-center justify-between text-[10px] text-zinc-500 pt-1 border-t border-zinc-900">
                          <span>Version: {pack.version}</span>
                          <span className="text-cyan-400">Validated</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tab 3: POSES & FRAMING */}
              {activeTab === "poses" && (
                <div className="mt-5 space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <h3 className="text-xs font-bold text-white uppercase tracking-wider">
                        Product-Aware Pose Resolver
                      </h3>
                      <p className="text-[11px] text-zinc-400">
                        Customer pose catalog resolved dynamically based on product SKU category.
                      </p>
                    </div>
                  </div>

                  {/* Product Type Filter Pills */}
                  <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-thin">
                    {PRODUCT_TYPES.map((pt) => {
                      const isSel = selectedProductType === pt.id;
                      const Icon = pt.icon;
                      return (
                        <button
                          key={pt.id}
                          onClick={() => setSelectedProductType(pt.id)}
                          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                            isSel
                              ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/50"
                              : "bg-zinc-950 text-zinc-400 border-zinc-800 hover:text-white hover:bg-zinc-900"
                          }`}
                        >
                          <Icon className="w-3.5 h-3.5" />
                          <span>{pt.label}</span>
                        </button>
                      );
                    })}
                  </div>

                  {/* Poses List */}
                  {loadingPoses ? (
                    <div className="flex items-center justify-center p-8 bg-zinc-950 rounded-xl border border-zinc-800">
                      <Loader2 className="w-5 h-5 animate-spin text-cyan-400" />
                    </div>
                  ) : poses.length > 0 ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {poses.map((pose) => (
                        <div key={pose.id} className="bg-zinc-950 border border-zinc-800 p-3.5 rounded-xl space-y-1.5">
                          <div className="flex items-center justify-between">
                            <h4 className="text-xs font-bold text-white">{pose.label}</h4>
                            <span className="px-2 py-0.5 bg-zinc-900 border border-zinc-700 text-zinc-300 text-[9px] font-mono rounded-full uppercase">
                              {pose.recommended_framing?.replace("_", " ") || "Full Body"}
                            </span>
                          </div>
                          <p className="text-[11px] text-zinc-400 line-clamp-2">{pose.description}</p>
                          <div className="flex items-center justify-between text-[10px] text-zinc-500 pt-1 font-mono">
                            <span>Category: {pose.category}</span>
                            {pose.is_default && (
                              <span className="text-emerald-400 font-bold">DEFAULT</span>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-6 bg-zinc-950 border border-zinc-800 rounded-xl text-center text-xs text-zinc-400">
                      No poses returned for {selectedProductType}. Capability pack is active with catalog defaults.
                    </div>
                  )}
                </div>
              )}

              {/* Tab 4: STYLING & APPEARANCE */}
              {activeTab === "styling" && (
                <div className="mt-5 space-y-4 text-xs">
                  <div className="bg-zinc-950 border border-zinc-800 p-4 rounded-xl space-y-3">
                    <h3 className="font-bold text-white flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-cyan-400" />
                      <span>Dynamic Styling Options (Hair, Makeup, Expression)</span>
                    </h3>
                    <p className="text-[11px] text-zinc-400">
                      Allowed styling variations configured for Eliska Novak without altering core facial geometry.
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 pt-2">
                      <div className="bg-zinc-900 p-3 rounded-lg border border-zinc-800">
                        <span className="text-zinc-500 font-medium block mb-1">Hair Styles</span>
                        <ul className="space-y-1 text-zinc-200">
                          <li>• Sleek Straight (Default)</li>
                          <li>• Low Editorial Bun</li>
                          <li>• Soft Natural Wave</li>
                          <li>• High Ponytail</li>
                        </ul>
                      </div>

                      <div className="bg-zinc-900 p-3 rounded-lg border border-zinc-800">
                        <span className="text-zinc-500 font-medium block mb-1">Makeup Looks</span>
                        <ul className="space-y-1 text-zinc-200">
                          <li>• Natural Editorial (Default)</li>
                          <li>• Clean Dewy Glow</li>
                          <li>• Smokey Eye High Fashion</li>
                          <li>• Sculpted Bold Lip</li>
                        </ul>
                      </div>

                      <div className="bg-zinc-900 p-3 rounded-lg border border-zinc-800">
                        <span className="text-zinc-500 font-medium block mb-1">Expressions</span>
                        <ul className="space-y-1 text-zinc-200">
                          <li>• Neutral Editorial (Default)</li>
                          <li>• Soft Confident Smile</li>
                          <li>• High Intensity Runway Gaze</li>
                          <li>• Relaxed Serene</li>
                        </ul>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 5: IDENTITY DNA */}
              {activeTab === "identity" && (
                <div className="mt-5 space-y-3 text-xs bg-zinc-950 p-4 rounded-xl border border-zinc-800">
                  <h3 className="font-bold text-cyan-400 flex items-center gap-2">
                    <Lock className="w-4 h-4" />
                    <span>Facial Architecture & DNA (LOCKED)</span>
                  </h3>
                  <div className="grid grid-cols-2 gap-3 text-zinc-300">
                    <div><span className="text-zinc-500">Face Shape:</span> Oval Architectural</div>
                    <div><span className="text-zinc-500">Eye Color:</span> Deep Hazel-Green</div>
                    <div><span className="text-zinc-500">Nose Bridge:</span> Refined Straight</div>
                    <div><span className="text-zinc-500">Jawline:</span> Sculpted Angular</div>
                    <div><span className="text-zinc-500">Left Cheek Landmark:</span> Micro-beauty mark (0.5mm)</div>
                    <div><span className="text-zinc-500">Collarbone Symmetry:</span> High-Definition Natural</div>
                  </div>
                </div>
              )}

              {/* Tab 6: BODY ARCHITECTURE */}
              {activeTab === "body" && (
                <div className="mt-5 space-y-3 text-xs bg-zinc-950 p-4 rounded-xl border border-zinc-800">
                  <h3 className="font-bold text-purple-400 flex items-center gap-2">
                    <Dna className="w-4 h-4" />
                    <span>Structured Body Profile (LOCKED)</span>
                  </h3>
                  <div className="grid grid-cols-2 gap-3 text-zinc-300">
                    <div><span className="text-zinc-500">HEIGHT:</span> 178 cm</div>
                    <div><span className="text-zinc-500">STATURE:</span> Tall</div>
                    <div><span className="text-zinc-500">BODY ARCHETYPE:</span> High-Fashion Runway Slim</div>
                    <div><span className="text-zinc-500">PROPORTION PROFILE:</span> EE-F-002 Body V1</div>
                    <div><span className="text-zinc-500">SHOE SIZE:</span> EU 39 / US 8.5</div>
                    <div><span className="text-zinc-500">BUST/WAIST/HIP:</span> 84-60-89 cm</div>
                  </div>
                </div>
              )}

              {/* Tab 7: CANONICAL ANGLES */}
              {activeTab === "angles" && (
                <div className="mt-5 space-y-4">
                  <h4 className="text-xs font-bold text-white uppercase">Half Body Angle Set (5-Angle Grid)</h4>
                  <div className="grid grid-cols-5 gap-2 text-center text-[10px] font-mono">
                    {["L45", "L30", "FRONT", "R30", "R45"].map((ang) => (
                      <div key={ang} className="bg-zinc-950 border border-zinc-800 p-2 rounded-lg">
                        <span className="text-cyan-400 block mb-1">{ang}</span>
                        <div className="aspect-[3/4] bg-zinc-900 rounded flex items-center justify-center text-zinc-500">
                          {ang} 35mm
                        </div>
                      </div>
                    ))}
                  </div>

                  <h4 className="text-xs font-bold text-white uppercase pt-2">Full Body Angle Set (5-Angle Grid)</h4>
                  <div className="grid grid-cols-5 gap-2 text-center text-[10px] font-mono">
                    {["L45", "L30", "FRONT", "R30", "R45"].map((ang) => (
                      <div key={ang} className="bg-zinc-950 border border-zinc-800 p-2 rounded-lg">
                        <span className="text-cyan-400 block mb-1">{ang}</span>
                        <div className="aspect-[3/4] bg-zinc-900 rounded flex items-center justify-center text-zinc-500">
                          {ang} 50mm
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Tab 8: VERSION REGISTRY */}
              {activeTab === "versions" && (
                <div className="mt-5 space-y-3 text-xs">
                  <div className="bg-zinc-950 border border-cyan-500/40 p-4 rounded-xl flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-sm">Version 1.0 (Production Immutable Lock)</span>
                        <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 text-[10px] font-bold rounded-full border border-emerald-500/30">
                          ACTIVE PRODUCTION
                        </span>
                      </div>
                      <p className="text-[11px] text-zinc-400 mt-1">
                        Canonical Height: 178 cm • Stature: Tall • Archetype: High-Fashion Runway Slim
                      </p>
                      <span className="text-[10px] font-mono text-zinc-500">Locked ID: EE-F-002-V1.0</span>
                    </div>
                    <Lock className="w-5 h-5 text-cyan-400" />
                  </div>

                  <div className="bg-zinc-950 border border-zinc-800 p-3.5 rounded-xl flex items-center justify-between text-zinc-400">
                    <div>
                      <span className="font-medium text-zinc-300">Version 0.9 (Pre-Production Golden Candidate)</span>
                      <p className="text-[10px] text-zinc-500">Full 10-Angle Rig & LoRA Validation Cleared</p>
                    </div>
                    <span className="text-[10px] font-mono text-zinc-500">ARCHIVED</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
