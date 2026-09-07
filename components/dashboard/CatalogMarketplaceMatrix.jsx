"use client";

import React, { useState, useEffect } from "react";
import {
  ShoppingBag,
  Download,
  FileArchive,
  Layers,
  Sparkles,
  ShieldCheck,
  CheckCircle2,
  ExternalLink,
  Loader2,
  FileText,
  Camera,
  Eye,
  Check,
  Globe,
  Tag,
  ArrowRight,
  Boxes,
  Zap,
} from "lucide-react";
import { toast } from "react-hot-toast";
import { catalogExportApi } from "@/lib/catalogExportApi";

const MARKETPLACE_CHANNELS = [
  {
    id: "shopify",
    name: "Shopify Store",
    format: "CSV",
    type: "E-Commerce",
    color: "from-emerald-600/20 to-teal-500/20",
    borderColor: "border-emerald-500/40",
    badgeColor: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
    description: "Standard Shopify Product CSV with Variant options, HTML descriptions & CDN image links.",
    columns: ["Handle", "Title", "Body (HTML)", "Vendor", "Type", "Tags", "Variant SKU", "Image Src"],
  },
  {
    id: "amazon",
    name: "Amazon Marketplace",
    format: "CSV",
    type: "Marketplace",
    color: "from-amber-600/20 to-orange-500/20",
    borderColor: "border-amber-500/40",
    badgeColor: "bg-amber-500/10 text-amber-300 border-amber-500/30",
    description: "Amazon Flat File Inventory Template with item_sku, standard_price & main_image_url.",
    columns: ["item_sku", "item_name", "standard_price", "brand_name", "main_image_url", "other_image_url1"],
  },
  {
    id: "zalando",
    name: "Zalando Partner",
    format: "JSON",
    type: "European Fashion",
    color: "from-orange-600/20 to-red-500/20",
    borderColor: "border-orange-500/40",
    badgeColor: "bg-orange-500/10 text-orange-300 border-orange-500/30",
    description: "Zalando Direct Partner API JSON schema with seasonal silhouettes and multi-angle arrays.",
    columns: ["sku", "brand", "season", "silhouettes", "media_assets", "size_matrix"],
  },
  {
    id: "asos",
    name: "ASOS Marketplace",
    format: "CSV",
    type: "Global Retail",
    color: "from-purple-600/20 to-pink-500/20",
    borderColor: "border-purple-500/40",
    badgeColor: "bg-purple-500/10 text-purple-300 border-purple-500/30",
    description: "ASOS catalog format including garment colorways, UK sizing, and high-street editorial images.",
    columns: ["SKU", "Title", "Category", "Colorway", "Price_GBP", "Primary_Image", "Hero_Angle"],
  },
  {
    id: "farfetch",
    name: "Farfetch Luxury",
    format: "JSON",
    type: "Luxury Marketplace",
    color: "from-blue-600/20 to-indigo-500/20",
    borderColor: "border-blue-500/40",
    badgeColor: "bg-blue-500/10 text-blue-300 border-blue-500/30",
    description: "Farfetch Global Luxury JSON feed compliant with 4K asset resolution & designer lookbook standards.",
    columns: ["luxury_sku", "designer_name", "composition", "season_code", "4k_hires_images"],
  },
];

const CATALOG_ANGLES = [
  {
    id: "FRONT",
    label: "Front Full View",
    tag: "A-01",
    aspect: "3:4",
    description: "Clean straight-on catalogue pose showing full silhouette drape.",
    image: "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=600&auto=format&fit=crop&q=80",
  },
  {
    id: "HERO_45",
    label: "45° Hero Perspective",
    tag: "A-02",
    aspect: "3:4",
    description: "Dynamic three-quarter angle displaying waistline cut and motion.",
    image: "https://images.unsplash.com/photo-1539109136881-3be0616acf4b?w=600&auto=format&fit=crop&q=80",
  },
  {
    id: "SIDE",
    label: "Side Silhouette (90°)",
    tag: "A-03",
    aspect: "3:4",
    description: "Profile angle capturing depth, garment structure, and sleeve curvature.",
    image: "https://images.unsplash.com/photo-1509631179647-0177331693ae?w=600&auto=format&fit=crop&q=80",
  },
  {
    id: "BACK",
    label: "Back & Spine Fit",
    tag: "A-04",
    aspect: "3:4",
    description: "Full rear perspective detailing fastening, seam lines, and rear drape.",
    image: "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=600&auto=format&fit=crop&q=80",
  },
  {
    id: "MACRO",
    label: "Fabric Macro Close-up",
    tag: "A-05",
    aspect: "3:4",
    description: "Micro-texture shot highlighting weave pattern, stitching, and fabric sheen.",
    image: "https://images.unsplash.com/photo-1469334031218-e382a71b716b?w=600&auto=format&fit=crop&q=80",
  },
];

export default function CatalogMarketplaceMatrix({ brandId, jobId = 1 }) {
  const [selectedJobId, setSelectedJobId] = useState(jobId);
  const [selectedAngles, setSelectedAngles] = useState(["FRONT", "HERO_45", "SIDE", "BACK", "MACRO"]);
  const [activeAngleTab, setActiveAngleTab] = useState("FRONT");
  const [selectedMarketplaces, setSelectedMarketplaces] = useState(["shopify", "amazon", "zalando", "asos", "farfetch"]);
  const [activeFeedPreview, setActiveFeedPreview] = useState("shopify");
  const [isExporting, setIsExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  const [exportStage, setExportStage] = useState("");

  const toggleAngle = (angleId) => {
    if (selectedAngles.includes(angleId)) {
      if (selectedAngles.length === 1) {
        toast.error("At least one catalog angle must be selected.");
        return;
      }
      setSelectedAngles(selectedAngles.filter((a) => a !== angleId));
    } else {
      setSelectedAngles([...selectedAngles, angleId]);
    }
  };

  const toggleMarketplace = (mId) => {
    if (selectedMarketplaces.includes(mId)) {
      if (selectedMarketplaces.length === 1) {
        toast.error("At least one marketplace feed must be selected.");
        return;
      }
      setSelectedMarketplaces(selectedMarketplaces.filter((id) => id !== mId));
    } else {
      setSelectedMarketplaces([...selectedMarketplaces, mId]);
    }
  };

  const handleExportSingleFeed = (marketplaceId) => {
    const url = catalogExportApi.getMarketplaceFeedUrl(selectedJobId, marketplaceId);
    toast.success(`Exporting ${marketplaceId.toUpperCase()} feed...`);
    window.open(url, "_blank");
  };

  const handleExportMultiFeedZip = () => {
    setIsExporting(true);
    setExportProgress(15);
    setExportStage("Generating 5-channel marketplace feed files (CSV & JSON)...");

    setTimeout(() => {
      setExportProgress(45);
      setExportStage("Validating SKU taxonomy, barcode mappings & variant image arrays...");
    }, 1000);

    setTimeout(() => {
      setExportProgress(80);
      setExportStage("Sealing C2PA digital provenance manifests into batch ZIP...");
    }, 2000);

    setTimeout(() => {
      setExportProgress(100);
      setIsExporting(false);
      setExportStage("Batch ZIP ready! Downloading multi-feed archive...");
      const url = catalogExportApi.getMultiFeedZipUrl(selectedJobId);
      window.open(url, "_blank");
      toast.success("Multi-Marketplace Feeds ZIP bundle downloaded!");
    }, 2800);
  };

  const currentAngleData = CATALOG_ANGLES.find((a) => a.id === activeAngleTab) || CATALOG_ANGLES[0];
  const currentFeedData = MARKETPLACE_CHANNELS.find((m) => m.id === activeFeedPreview) || MARKETPLACE_CHANNELS[0];

  return (
    <div className="bg-zinc-950 border border-zinc-800/80 rounded-2xl p-6 text-zinc-100 shadow-2xl space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-zinc-800/80 pb-6">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide bg-gradient-to-r from-blue-500/20 to-indigo-500/20 text-blue-300 border border-blue-500/30">
              WF-CATALOG-001 · Section 16
            </span>
            <span className="flex items-center gap-1 text-xs text-zinc-400 bg-zinc-900 px-2 py-0.5 rounded-md border border-zinc-800">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
              5 Marketplace Feeds Synced
            </span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-zinc-100 via-zinc-200 to-zinc-400 bg-clip-text text-transparent">
            Multi-Marketplace Catalog Sync Matrix
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Automated SKU feed formatting for Shopify, Amazon, Zalando, ASOS & Farfetch with 5-angle pack sets.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleExportMultiFeedZip}
            disabled={isExporting}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-blue-500 via-indigo-500 to-blue-600 hover:from-blue-400 hover:to-indigo-500 text-zinc-950 font-bold text-xs shadow-xl shadow-blue-500/20 disabled:opacity-50 transition-all transform active:scale-[0.98]"
          >
            {isExporting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-zinc-950" />
                Packaging ZIP Feeds...
              </>
            ) : (
              <>
                <FileArchive className="w-4 h-4 text-zinc-950" />
                Export Multi-Feed (.ZIP)
              </>
            )}
          </button>
        </div>
      </div>

      {/* Progress Telemetry */}
      {isExporting && (
        <div className="bg-zinc-900/90 border border-blue-500/30 rounded-xl p-4 space-y-2 animate-pulse">
          <div className="flex items-center justify-between text-xs font-semibold">
            <span className="flex items-center gap-2 text-blue-400">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              {exportStage}
            </span>
            <span className="text-zinc-400 font-mono">{exportProgress}%</span>
          </div>
          <div className="w-full bg-zinc-800 rounded-full h-2 overflow-hidden">
            <div
              className="bg-gradient-to-r from-blue-500 to-indigo-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${exportProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* 5-Angle SKU Pack Gallery */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Camera className="w-3.5 h-3.5 text-blue-400" />
            5 Standard Catalog Angle Pack ({selectedAngles.length}/5 Active)
          </label>
          <span className="text-xs text-zinc-500 font-mono">3:4 Studio Ratio</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {CATALOG_ANGLES.map((angle) => {
            const isSelected = selectedAngles.includes(angle.id);
            const isActive = activeAngleTab === angle.id;

            return (
              <div
                key={angle.id}
                onClick={() => setActiveAngleTab(angle.id)}
                className={`group cursor-pointer rounded-xl p-3 border transition-all ${
                  isActive
                    ? "bg-zinc-900 border-blue-500/60 shadow-lg shadow-blue-500/10"
                    : isSelected
                    ? "bg-zinc-950 border-zinc-800 hover:border-zinc-700"
                    : "bg-zinc-950/40 border-zinc-900 opacity-40"
                }`}
              >
                <div className="relative aspect-[3/4] rounded-lg overflow-hidden border border-zinc-800 mb-2">
                  <img src={angle.image} alt={angle.label} className="w-full h-full object-cover" />
                  <span className="absolute top-2 left-2 px-1.5 py-0.5 rounded text-[9px] font-mono font-bold bg-black/70 text-blue-300 border border-white/10">
                    {angle.tag}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleAngle(angle.id);
                    }}
                    className={`absolute top-2 right-2 w-5 h-5 rounded-md flex items-center justify-center border transition ${
                      isSelected
                        ? "bg-blue-500 border-blue-500 text-zinc-950"
                        : "bg-black/60 border-zinc-700 text-zinc-400"
                    }`}
                  >
                    {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                  </button>
                </div>
                <div className="text-xs font-semibold text-zinc-200 truncate">{angle.label}</div>
                <div className="text-[10px] text-zinc-500 mt-0.5 truncate">{angle.description}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Main Grid: Marketplace Sync Feeds & Sample Code Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 pt-2">
        {/* Left Column: 5 Marketplace Cards (6 cols) */}
        <div className="lg:col-span-6 space-y-3">
          <label className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Globe className="w-3.5 h-3.5 text-blue-400" />
            Supported Marketplace Channels ({selectedMarketplaces.length}/5)
          </label>

          <div className="space-y-2.5">
            {MARKETPLACE_CHANNELS.map((channel) => {
              const isSelected = selectedMarketplaces.includes(channel.id);
              const isPreviewing = activeFeedPreview === channel.id;

              return (
                <div
                  key={channel.id}
                  onClick={() => setActiveFeedPreview(channel.id)}
                  className={`cursor-pointer rounded-xl p-4 border transition-all flex items-start justify-between gap-3 ${
                    isPreviewing
                      ? `bg-zinc-900 ${channel.borderColor} shadow-lg shadow-black/40`
                      : "bg-zinc-950/60 border-zinc-800/80 hover:border-zinc-700"
                  }`}
                >
                  <div className="space-y-1 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-zinc-100">{channel.name}</span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-semibold border ${channel.badgeColor}`}>
                        {channel.format}
                      </span>
                      <span className="text-[10px] text-zinc-500 font-medium">({channel.type})</span>
                    </div>
                    <p className="text-[11px] text-zinc-400 leading-relaxed">{channel.description}</p>
                    <div className="flex items-center gap-1.5 flex-wrap pt-1">
                      {channel.columns.slice(0, 4).map((col, idx) => (
                        <span
                          key={idx}
                          className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-zinc-800/70 text-zinc-400 border border-zinc-700/60"
                        >
                          {col}
                        </span>
                      ))}
                      {channel.columns.length > 4 && (
                        <span className="text-[9px] text-zinc-500 font-mono">+{channel.columns.length - 4} cols</span>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-col items-end gap-2 shrink-0">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleExportSingleFeed(channel.id);
                      }}
                      className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-medium border border-zinc-700 transition"
                      title={`Download ${channel.format}`}
                    >
                      <Download className="w-3 h-3" />
                      {channel.format}
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleMarketplace(channel.id);
                      }}
                      className={`w-5 h-5 rounded-md flex items-center justify-center border transition ${
                        isSelected
                          ? "bg-blue-500 border-blue-500 text-zinc-950"
                          : "bg-zinc-900 border-zinc-700 text-zinc-500"
                      }`}
                    >
                      {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Right Column: Feed Live Preview Schema / JSON (6 cols) */}
        <div className="lg:col-span-6 bg-zinc-900/40 border border-zinc-800/80 rounded-2xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3 mb-4">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-400" />
                <span className="text-xs font-semibold text-zinc-200">
                  {currentFeedData.name} Output Schema
                </span>
              </div>
              <span className="text-[10px] font-mono text-zinc-500">Live Manifest View</span>
            </div>

            {/* Code / Table Preview */}
            <div className="bg-zinc-950 border border-zinc-800 rounded-xl p-3.5 font-mono text-xs overflow-x-auto max-h-[360px] text-zinc-300">
              {currentFeedData.format === "JSON" ? (
                <pre className="text-[11px] leading-relaxed text-blue-300">
{`{
  "marketplace": "${currentFeedData.id}",
  "version": "2.4",
  "job_id": ${selectedJobId},
  "exported_at": "${new Date().toISOString()}",
  "catalog_skus": [
    {
      "sku_tag": "SKU-AQU-2027",
      "brand_name": "Mode Lens Capsule",
      "category": "High Fashion",
      "angles": ${JSON.stringify(selectedAngles)},
      "media_assets": [
        "https://cdn.modelens.ai/output/${selectedJobId}/front.jpg",
        "https://cdn.modelens.ai/output/${selectedJobId}/hero_45.jpg"
      ],
      "c2pa_manifest_id": "urn:c2pa:modelens:cat_8892"
    }
  ]
}`}
                </pre>
              ) : (
                <div className="space-y-2 text-[11px]">
                  <div className="text-zinc-500 border-b border-zinc-800 pb-1">
                    # CSV Header Row:
                  </div>
                  <div className="text-emerald-400">
                    {currentFeedData.columns.join(", ")}
                  </div>
                  <div className="text-zinc-500 border-b border-zinc-800 pt-2 pb-1">
                    # Sample Data Row:
                  </div>
                  <div className="text-zinc-300">
                    SKU-AQU-2027, "Silk Draped Evening Gown", "&lt;p&gt;Cinematic high-fashion...&lt;/p&gt;", "Mode Lens", "Gown", "Autumn 27", "$1200.00", "https://cdn.modelens.ai/output/${selectedJobId}/front.jpg"
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Footer Metadata */}
          <div className="mt-4 pt-4 border-t border-zinc-800/80 flex items-center justify-between text-xs text-zinc-400">
            <div className="flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Manifest sealed with C2PA digital provenance.</span>
            </div>
            <span className="font-mono text-zinc-500 text-[11px]">5 Feeds Ready</span>
          </div>
        </div>
      </div>
    </div>
  );
}
