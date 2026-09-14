"use client";

import React, { useState, useEffect } from "react";
import { characterRegistryApi } from "@/lib/characterRegistryApi";
import { 
  User, 
  Sparkles, 
  ShieldCheck, 
  Activity, 
  Sliders, 
  CheckCircle2, 
  AlertCircle, 
  Plus, 
  X, 
  Loader2, 
  Cpu, 
  Dna, 
  Scissors, 
  Flame, 
  ChevronRight,
  Layers
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "react-hot-toast";

const LIFECYCLE_STATUSES = [
  { code: "CHAR_CONCEPT", label: "Concept Draft", bg: "bg-zinc-800 text-zinc-300 border-zinc-700" },
  { code: "CHAR_DISCOVERY", label: "Discovery Phase", bg: "bg-blue-950/80 text-blue-300 border-blue-800" },
  { code: "CHAR_MASTER_SELECTED", label: "Master Selected", bg: "bg-indigo-950/80 text-indigo-300 border-indigo-800" },
  { code: "CHAR_GOLDEN", label: "Golden Candidate", bg: "bg-amber-950/80 text-amber-300 border-amber-800" },
  { code: "CHAR_ACTIVE", label: "Production Active", bg: "bg-emerald-950/80 text-emerald-300 border-emerald-800" },
  { code: "CHAR_RETIRED", label: "Retired", bg: "bg-rose-950/80 text-rose-300 border-rose-800" },
];

export default function CharacterRegistryManager({ initialCharacterId = null }) {
  const [characters, setCharacters] = useState([]);
  const [selectedCharId, setSelectedCharId] = useState(initialCharacterId);
  const [characterDetails, setCharacterDetails] = useState(null);
  
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [activeTab, setActiveTab] = useState("identity"); // identity | body | skin | hair | runtime
  
  // New Character Identity Modal
  const [isIdentityModalOpen, setIsIdentityModalOpen] = useState(false);
  const [newCharId, setNewCharId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [internalName, setInternalName] = useState("");
  const [ageAnchor, setAgeAnchor] = useState(25);
  const [faceShape, setFaceShape] = useState("oval");
  const [eyeShape, setEyeShape] = useState("almond");
  const [jawWidth, setJawWidth] = useState("medium");
  const [chinShape, setChinShape] = useState("tapered");
  const [isSubmittingIdentity, setIsSubmittingIdentity] = useState(false);

  // Profile Edit Modals
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [editProfileType, setEditProfileType] = useState(null); // body | skin | hair | runtime
  const [profileFormData, setProfileFormData] = useState({});
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  // Load characters list
  const fetchCharacters = async () => {
    try {
      setLoadingList(true);
      const res = await characterRegistryApi.listCharacters();
      const list = res.characters || [];
      setCharacters(list);
      if (list.length > 0 && !selectedCharId) {
        setSelectedCharId(list[0].character_id);
      }
    } catch (err) {
      toast.error("Failed to load character registry");
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    fetchCharacters();
  }, []);

  // Fetch full details when selectedCharId changes
  useEffect(() => {
    if (!selectedCharId) return;
    async function loadDetails() {
      try {
        setLoadingDetails(true);
        const res = await characterRegistryApi.getCharacter(selectedCharId);
        setCharacterDetails(res);
      } catch (err) {
        toast.error(`Failed to load details for ${selectedCharId}`);
      } finally {
        setLoadingDetails(false);
      }
    }
    loadDetails();
  }, [selectedCharId]);

  // Handle Lifecycle Status Transition
  const handleStatusChange = async (newStatus) => {
    if (!selectedCharId) return;
    try {
      await characterRegistryApi.updateStatus(selectedCharId, newStatus);
      toast.success(`Character status updated to ${newStatus}`);
      fetchCharacters();
      // Reload character details
      const res = await characterRegistryApi.getCharacter(selectedCharId);
      setCharacterDetails(res);
    } catch (err) {
      toast.error(err.message || "Failed to update status");
    }
  };

  // Handle Create Identity
  const handleCreateIdentity = async (e) => {
    e.preventDefault();
    if (!newCharId.trim()) {
      toast.error("Character ID is required (e.g. EE-F-003)");
      return;
    }
    setIsSubmittingIdentity(true);
    try {
      await characterRegistryApi.createIdentityProfile({
        character_id: newCharId.trim(),
        display_name: displayName.trim() || newCharId.trim(),
        internal_name: internalName.trim() || newCharId.trim(),
        age_anchor: parseInt(ageAnchor) || 25,
        face_shape: faceShape,
        eye_shape: eyeShape,
        jaw_width: jawWidth,
        chin_shape: chinShape,
      });
      toast.success("Character Identity Profile created!");
      setIsIdentityModalOpen(false);
      setNewCharId("");
      setDisplayName("");
      setInternalName("");
      fetchCharacters();
      setSelectedCharId(newCharId.trim());
    } catch (err) {
      toast.error(err.message || "Failed to create character identity");
    } finally {
      setIsSubmittingIdentity(false);
    }
  };

  // Open Edit Profile Form
  const openProfileEditor = (type) => {
    setEditProfileType(type);
    if (type === "body") {
      const b = characterDetails?.body_profile || {};
      setProfileFormData({
        body_profile_id: b.body_profile_id || `BODY_${selectedCharId}_01`,
        height_cm: b.height_cm || 175,
        height_band: b.height_band || "175_180CM",
        build_code: b.build_code || "SLENDER",
        frame_code: b.frame_code || "NARROW",
        head_body_ratio: b.head_body_ratio || 7.5,
        shoulders_width: b.shoulders_width || "38CM",
        torso_length: b.torso_length || "MEDIUM",
        leg_proportion: b.leg_proportion || "LONG",
        arm_length: b.arm_length || "STANDARD",
      });
    } else if (type === "skin") {
      const s = characterDetails?.skin_profile || {};
      setProfileFormData({
        skin_profile_id: s.skin_profile_id || `SKIN_${selectedCharId}_01`,
        depth_code: s.depth_code || "FAIR_LIGHT",
        undertone_code: s.undertone_code || "NEUTRAL_WARM",
        chroma_code: s.chroma_code || "MEDIUM",
        pore_density: s.pore_density || "FINE_GRAIN",
        microtexture: s.microtexture || "NATURAL_SPECULAR",
        under_eye_texture: s.under_eye_texture || "SOFT",
        sebum_code: s.sebum_code || "SATIN",
        age_profile: s.age_profile || "YOUNG_ADULT",
      });
    } else if (type === "hair") {
      const h = characterDetails?.hair_profile || {};
      setProfileFormData({
        hair_dna_id: h.hair_dna_id || `HAIR_${selectedCharId}_01`,
        natural_color: h.natural_color || "DARK_BROWN",
        undertone: h.undertone || "WARM_CHESTNUT",
        hairline: h.hairline || "NATURAL_SOFT",
        density: h.density || "MEDIUM_HIGH",
        strand_thickness: h.strand_thickness || "FINE",
        natural_texture: h.natural_texture || "WAVY_TYPE_2A",
        canonical_length: h.canonical_length || "SHOULDER_LENGTH",
        canonical_part: h.canonical_part || "LEFT_OFF_CENTER",
      });
    } else if (type === "runtime") {
      const r = characterDetails?.runtime_profile || {};
      setProfileFormData({
        runtime_profile_id: r.runtime_profile_id || `RUN_${selectedCharId}_01`,
        character_version: r.character_version || "1.0",
        production_model_alias: r.production_model_alias || `lora_modelens_${selectedCharId.toLowerCase()}_v1`,
        default_strength: r.default_strength || 0.78,
      });
    }
    setIsEditingProfile(true);
  };

  // Save Profile Data
  const handleSaveProfile = async (e) => {
    e.preventDefault();
    if (!selectedCharId || !editProfileType) return;
    setIsSavingProfile(true);
    try {
      const payload = { ...profileFormData, character_id: selectedCharId };
      if (editProfileType === "body") {
        await characterRegistryApi.createBodyProfile(selectedCharId, payload);
      } else if (editProfileType === "skin") {
        await characterRegistryApi.createSkinProfile(selectedCharId, payload);
      } else if (editProfileType === "hair") {
        await characterRegistryApi.createHairProfile(selectedCharId, payload);
      } else if (editProfileType === "runtime") {
        await characterRegistryApi.createRuntimeProfile(selectedCharId, payload);
      }
      toast.success(`${editProfileType.toUpperCase()} profile updated!`);
      setIsEditingProfile(false);
      // Refresh details
      const res = await characterRegistryApi.getCharacter(selectedCharId);
      setCharacterDetails(res);
    } catch (err) {
      toast.error(err.message || "Failed to save profile");
    } finally {
      setIsSavingProfile(false);
    }
  };

  const identity = characterDetails?.identity || {};
  const body = characterDetails?.body_profile || {};
  const skin = characterDetails?.skin_profile || {};
  const hair = characterDetails?.hair_profile || {};
  const runtime = characterDetails?.runtime_profile || {};

  const currentStatusObj = LIFECYCLE_STATUSES.find(s => s.code === identity.status) || LIFECYCLE_STATUSES[0];

  return (
    <div className="space-y-6">
      {/* Top Controller Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-5 rounded-2xl bg-gradient-to-r from-zinc-950 via-purple-950/30 to-zinc-950 border border-purple-800/40">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
            <User className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              Character Taxonomy & Profile Registry
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-purple-950 text-purple-300 border border-purple-800">
                P2 Standardized
              </span>
            </h2>
            <p className="text-xs text-zinc-400">
              Manage multi-profile character parameters across Identity, Body, Skin, Hair DNA, and Runtime LoRAs.
            </p>
          </div>
        </div>

        <button
          onClick={() => setIsIdentityModalOpen(true)}
          className="px-4 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold transition flex items-center gap-1.5 shadow-lg shadow-purple-600/20 shrink-0"
        >
          <Plus size={14} />
          New Character Identity
        </button>
      </div>

      {/* Main Split Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left Characters Selector */}
        <div className="lg:col-span-1 bg-zinc-950 border border-zinc-850 rounded-2xl p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-zinc-850 pb-2">
            <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Registered Models</span>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-zinc-900 text-purple-300 font-bold">
              {characters.length}
            </span>
          </div>

          {loadingList ? (
            <div className="flex items-center justify-center p-8 text-purple-400">
              <Loader2 className="animate-spin" size={20} />
            </div>
          ) : characters.length === 0 ? (
            <p className="text-xs text-zinc-500 p-4 text-center">No characters registered yet.</p>
          ) : (
            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {characters.map((c) => {
                const isSelected = c.character_id === selectedCharId;
                const statusObj = LIFECYCLE_STATUSES.find(s => s.code === c.status) || LIFECYCLE_STATUSES[0];
                return (
                  <button
                    key={c.character_id}
                    onClick={() => setSelectedCharId(c.character_id)}
                    className={`w-full text-left p-3 rounded-xl border transition flex items-center justify-between cursor-pointer ${
                      isSelected
                        ? "bg-purple-950/40 border-purple-500/60 text-white shadow-md"
                        : "bg-zinc-900/50 border-zinc-850 text-zinc-300 hover:border-zinc-700"
                    }`}
                  >
                    <div>
                      <span className="font-bold text-xs block text-white font-mono">{c.character_id}</span>
                      <span className="text-[11px] text-zinc-400">{c.display_name || c.internal_name}</span>
                    </div>
                    <div className="text-right">
                      <span className={`text-[9px] font-mono px-2 py-0.5 rounded border ${statusObj.bg}`}>
                        {statusObj.label}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Multi-Profile Inspector */}
        <div className="lg:col-span-3 bg-zinc-950 border border-zinc-850 rounded-2xl p-6 space-y-6">
          {loadingDetails ? (
            <div className="flex h-64 items-center justify-center text-purple-400">
              <Loader2 className="animate-spin" size={24} />
            </div>
          ) : !characterDetails || !identity.character_id ? (
            <div className="text-center py-16 text-zinc-500 space-y-2">
              <User className="mx-auto text-zinc-700" size={32} />
              <p className="text-xs">Select a character from the list to inspect profiles.</p>
            </div>
          ) : (
            <>
              {/* Character Header Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-zinc-850">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-lg font-bold text-white font-mono">{identity.character_id}</span>
                    <span className="text-sm text-zinc-400">({identity.display_name || identity.internal_name})</span>
                  </div>
                  <p className="text-xs text-zinc-500">
                    Age Anchor: <span className="text-zinc-300 font-semibold">{identity.age_anchor || 25} yo</span> · Face: <span className="text-zinc-300 font-semibold">{identity.face_shape || "Oval"}</span>
                  </p>
                </div>

                {/* Lifecycle Switcher */}
                <div className="flex items-center gap-2 bg-zinc-900 p-1.5 rounded-xl border border-zinc-800">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 pl-2">Lifecycle:</span>
                  <select
                    value={identity.status || "CHAR_CONCEPT"}
                    onChange={(e) => handleStatusChange(e.target.value)}
                    className="bg-zinc-950 text-xs font-mono text-amber-300 font-bold px-3 py-1.5 rounded-lg border border-zinc-800 outline-none cursor-pointer"
                  >
                    {LIFECYCLE_STATUSES.map((s) => (
                      <option key={s.code} value={s.code}>
                        {s.label} ({s.code})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Profile Navigation Tabs */}
              <div className="flex flex-wrap gap-2 border-b border-zinc-850 pb-3">
                <button
                  onClick={() => setActiveTab("identity")}
                  className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 ${
                    activeTab === "identity" ? "bg-purple-600 text-white shadow-md shadow-purple-600/20" : "bg-zinc-900 text-zinc-400 hover:text-white"
                  }`}
                >
                  <User size={14} />
                  Identity Profile
                </button>
                <button
                  onClick={() => setActiveTab("body")}
                  className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 ${
                    activeTab === "body" ? "bg-purple-600 text-white shadow-md shadow-purple-600/20" : "bg-zinc-900 text-zinc-400 hover:text-white"
                  }`}
                >
                  <Dna size={14} />
                  Body Profile
                </button>
                <button
                  onClick={() => setActiveTab("skin")}
                  className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 ${
                    activeTab === "skin" ? "bg-purple-600 text-white shadow-md shadow-purple-600/20" : "bg-zinc-900 text-zinc-400 hover:text-white"
                  }`}
                >
                  <Sparkles size={14} />
                  Skin Profile
                </button>
                <button
                  onClick={() => setActiveTab("hair")}
                  className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 ${
                    activeTab === "hair" ? "bg-purple-600 text-white shadow-md shadow-purple-600/20" : "bg-zinc-900 text-zinc-400 hover:text-white"
                  }`}
                >
                  <Scissors size={14} />
                  Hair DNA
                </button>
                <button
                  onClick={() => setActiveTab("runtime")}
                  className={`px-3.5 py-2 rounded-xl text-xs font-semibold transition flex items-center gap-1.5 ${
                    activeTab === "runtime" ? "bg-purple-600 text-white shadow-md shadow-purple-600/20" : "bg-zinc-900 text-zinc-400 hover:text-white"
                  }`}
                >
                  <Cpu size={14} />
                  Runtime & LoRA
                </button>
              </div>

              {/* Tab 1: Identity */}
              {activeTab === "identity" && (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                    <ProfileMetricCard label="Face Shape" value={identity.face_shape || "Oval"} />
                    <ProfileMetricCard label="Eye Shape" value={identity.eye_shape || "Almond"} />
                    <ProfileMetricCard label="Eye Spacing" value={identity.eye_spacing || "Canonical (62mm)"} />
                    <ProfileMetricCard label="Nose Bridge" value={identity.nose_bridge || "Straight Medium"} />
                    <ProfileMetricCard label="Cheekbones" value={identity.cheekbone_height || "High Soft"} />
                    <ProfileMetricCard label="Jaw Width" value={identity.jaw_width || "Tapered Medium"} />
                    <ProfileMetricCard label="Chin Shape" value={identity.chin_shape || "Soft Point"} />
                    <ProfileMetricCard label="Age Anchor" value={`${identity.age_anchor || 25} years`} />
                    <ProfileMetricCard label="Golden Certified" value={identity.golden_character_version ? "v1.0" : "Candidate"} />
                  </div>
                </div>
              )}

              {/* Tab 2: Body */}
              {activeTab === "body" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">Body Proportions Profile</h4>
                    <button
                      onClick={() => openProfileEditor("body")}
                      className="px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-xs font-semibold text-purple-300 transition"
                    >
                      {body.body_profile_id ? "Edit Body Profile" : "+ Create Body Profile"}
                    </button>
                  </div>

                  {!body.body_profile_id ? (
                    <div className="p-8 text-center bg-zinc-900/40 rounded-xl border border-dashed border-zinc-800 text-zinc-500 text-xs">
                      No Body Profile registered. Click above to add body measurements & height bands.
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                      <ProfileMetricCard label="Height (cm)" value={`${body.height_cm || 175} cm`} />
                      <ProfileMetricCard label="Height Band" value={body.height_band || "175_180CM"} />
                      <ProfileMetricCard label="Build Code" value={body.build_code || "Slender"} />
                      <ProfileMetricCard label="Frame Code" value={body.frame_code || "Narrow"} />
                      <ProfileMetricCard label="Head/Body Ratio" value={`1:${body.head_body_ratio || 7.5}`} />
                      <ProfileMetricCard label="Shoulders Width" value={body.shoulders_width || "38cm"} />
                      <ProfileMetricCard label="Torso Length" value={body.torso_length || "Medium"} />
                      <ProfileMetricCard label="Leg Proportion" value={body.leg_proportion || "Long"} />
                      <ProfileMetricCard label="Arm Length" value={body.arm_length || "Standard"} />
                    </div>
                  )}
                </div>
              )}

              {/* Tab 3: Skin */}
              {activeTab === "skin" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">Skin Texture & Undertone Profile</h4>
                    <button
                      onClick={() => openProfileEditor("skin")}
                      className="px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-xs font-semibold text-purple-300 transition"
                    >
                      {skin.skin_profile_id ? "Edit Skin Profile" : "+ Create Skin Profile"}
                    </button>
                  </div>

                  {!skin.skin_profile_id ? (
                    <div className="p-8 text-center bg-zinc-900/40 rounded-xl border border-dashed border-zinc-800 text-zinc-500 text-xs">
                      No Skin Profile registered. Click above to configure microtexture & undertones.
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                      <ProfileMetricCard label="Depth Code" value={skin.depth_code || "Fair-Light"} />
                      <ProfileMetricCard label="Undertone" value={skin.undertone_code || "Neutral Warm"} />
                      <ProfileMetricCard label="Chroma Code" value={skin.chroma_code || "Medium"} />
                      <ProfileMetricCard label="Pore Density" value={skin.pore_density || "Fine Grain"} />
                      <ProfileMetricCard label="Microtexture" value={skin.microtexture || "Natural Specular"} />
                      <ProfileMetricCard label="Under Eye" value={skin.under_eye_texture || "Soft Grain"} />
                      <ProfileMetricCard label="Sebum Code" value={skin.sebum_code || "Satin"} />
                      <ProfileMetricCard label="Age Profile" value={skin.age_profile || "Young Adult"} />
                    </div>
                  )}
                </div>
              )}

              {/* Tab 4: Hair */}
              {activeTab === "hair" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">Hair DNA & Style Profile</h4>
                    <button
                      onClick={() => openProfileEditor("hair")}
                      className="px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-xs font-semibold text-purple-300 transition"
                    >
                      {hair.hair_dna_id ? "Edit Hair DNA" : "+ Create Hair DNA"}
                    </button>
                  </div>

                  {!hair.hair_dna_id ? (
                    <div className="p-8 text-center bg-zinc-900/40 rounded-xl border border-dashed border-zinc-800 text-zinc-500 text-xs">
                      No Hair Profile registered. Click above to configure natural color & hairline.
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                      <ProfileMetricCard label="Natural Color" value={hair.natural_color || "Dark Brown"} />
                      <ProfileMetricCard label="Undertone" value={hair.undertone || "Chestnut"} />
                      <ProfileMetricCard label="Hairline" value={hair.hairline || "Soft Natural"} />
                      <ProfileMetricCard label="Density" value={hair.density || "Medium-High"} />
                      <ProfileMetricCard label="Strand Thickness" value={hair.strand_thickness || "Fine"} />
                      <ProfileMetricCard label="Natural Texture" value={hair.natural_texture || "Wavy 2A"} />
                      <ProfileMetricCard label="Canonical Length" value={hair.canonical_length || "Shoulder"} />
                      <ProfileMetricCard label="Canonical Part" value={hair.canonical_part || "Left Off-Center"} />
                    </div>
                  )}
                </div>
              )}

              {/* Tab 5: Runtime */}
              {activeTab === "runtime" && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider">Production Model & LoRA Runtime</h4>
                    <button
                      onClick={() => openProfileEditor("runtime")}
                      className="px-3 py-1.5 rounded-lg bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-xs font-semibold text-purple-300 transition"
                    >
                      {runtime.runtime_profile_id ? "Edit Runtime Profile" : "+ Create Runtime Profile"}
                    </button>
                  </div>

                  {!runtime.runtime_profile_id ? (
                    <div className="p-8 text-center bg-zinc-900/40 rounded-xl border border-dashed border-zinc-800 text-zinc-500 text-xs">
                      No Runtime Profile registered. Click above to configure production LoRA alias & default strength.
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <ProfileMetricCard label="Production Model Alias" value={runtime.production_model_alias || "lora_modelens_v1"} />
                      <ProfileMetricCard label="Default Strength" value={`${runtime.default_strength || 0.78}`} />
                      <ProfileMetricCard label="Character Version" value={`v${runtime.character_version || "1.0"}`} />
                      <ProfileMetricCard label="Status" value="Approved for Production Workflows" />
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Modal 1: Create Identity Profile */}
      <AnimatePresence>
        {isIdentityModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 0.5 }} exit={{ opacity: 0 }} onClick={() => setIsIdentityModalOpen(false)} className="fixed inset-0 bg-black" />
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-lg p-6 relative z-10 shadow-2xl space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <User className="text-purple-400" size={18} />
                  New Character Identity
                </h3>
                <button onClick={() => setIsIdentityModalOpen(false)} className="text-zinc-500 hover:text-zinc-300 p-1"><X size={16} /></button>
              </div>

              <form onSubmit={handleCreateIdentity} className="space-y-4">
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-zinc-300">Character ID (Required)</label>
                  <input type="text" required value={newCharId} onChange={(e) => setNewCharId(e.target.value)} placeholder="e.g. EE-F-003" className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white font-mono outline-none focus:border-purple-500" />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Display Name</label>
                    <input type="text" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="e.g. Maya Lin" className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white outline-none focus:border-purple-500" />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Age Anchor</label>
                    <input type="number" value={ageAnchor} onChange={(e) => setAgeAnchor(e.target.value)} className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white outline-none focus:border-purple-500" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Face Shape</label>
                    <select value={faceShape} onChange={(e) => setFaceShape(e.target.value)} className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white outline-none">
                      <option value="oval">Oval</option>
                      <option value="round">Round</option>
                      <option value="square">Square</option>
                      <option value="heart">Heart</option>
                      <option value="diamond">Diamond</option>
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-zinc-300">Eye Shape</label>
                    <select value={eyeShape} onChange={(e) => setEyeShape(e.target.value)} className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white outline-none">
                      <option value="almond">Almond</option>
                      <option value="round">Round</option>
                      <option value="monolid">Monolid</option>
                      <option value="hooded">Hooded</option>
                    </select>
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
                  <button type="button" onClick={() => setIsIdentityModalOpen(false)} className="px-4 py-2 rounded-xl bg-zinc-800 text-zinc-300 text-xs font-semibold">Cancel</button>
                  <button type="submit" disabled={isSubmittingIdentity} className="px-4 py-2 rounded-xl bg-purple-600 text-white text-xs font-semibold flex items-center gap-1">
                    {isSubmittingIdentity ? <Loader2 className="animate-spin" size={14} /> : "Create Identity Profile"}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Modal 2: Edit Profile Form */}
      <AnimatePresence>
        {isEditingProfile && (
          <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 0.5 }} exit={{ opacity: 0 }} onClick={() => setIsEditingProfile(false)} className="fixed inset-0 bg-black" />
            <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.95 }} className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-lg p-6 relative z-10 shadow-2xl space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-base font-bold text-white uppercase font-mono flex items-center gap-2">
                  <Sliders className="text-purple-400" size={18} />
                  Configure {editProfileType?.toUpperCase()} Profile ({selectedCharId})
                </h3>
                <button onClick={() => setIsEditingProfile(false)} className="text-zinc-500 hover:text-zinc-300 p-1"><X size={16} /></button>
              </div>

              <form onSubmit={handleSaveProfile} className="space-y-4">
                {Object.keys(profileFormData).map((key) => (
                  <div key={key} className="space-y-1">
                    <label className="text-[11px] font-mono text-zinc-400 uppercase tracking-wider">{key.replace(/_/g, " ")}</label>
                    <input
                      type="text"
                      value={profileFormData[key] || ""}
                      onChange={(e) => setProfileFormData({ ...profileFormData, [key]: e.target.value })}
                      className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white outline-none focus:border-purple-500 font-mono"
                    />
                  </div>
                ))}

                <div className="flex justify-end gap-2 pt-3 border-t border-zinc-800">
                  <button type="button" onClick={() => setIsEditingProfile(false)} className="px-4 py-2 rounded-xl bg-zinc-800 text-zinc-300 text-xs font-semibold">Cancel</button>
                  <button type="submit" disabled={isSavingProfile} className="px-4 py-2 rounded-xl bg-purple-600 text-white text-xs font-semibold flex items-center gap-1">
                    {isSavingProfile ? <Loader2 className="animate-spin" size={14} /> : "Save Profile Data"}
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

function ProfileMetricCard({ label, value }) {
  return (
    <div className="p-3.5 rounded-xl bg-zinc-900/60 border border-zinc-850 space-y-1">
      <span className="text-[10px] font-mono text-zinc-500 uppercase tracking-wider block">{label}</span>
      <span className="text-xs font-bold text-white font-mono block truncate">{value}</span>
    </div>
  );
}
