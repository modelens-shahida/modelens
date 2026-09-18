/**
 * ModeLens Character Architecture & Schema Specifications
 * Shahida Directive Compliance: Reusable, data-driven template for all production characters.
 */

export const CHARACTER_STATUS = {
  DEVELOPMENT: { label: "DEVELOPMENT", color: "bg-amber-500/10 text-amber-400 border-amber-500/30" },
  VALIDATION: { label: "VALIDATION", color: "bg-cyan-500/10 text-cyan-400 border-cyan-500/30" },
  LOCKED: { label: "LOCKED", color: "bg-indigo-500/10 text-indigo-400 border-indigo-500/30" },
  PRODUCTION: { label: "PRODUCTION", color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" },
  ARCHIVED: { label: "ARCHIVED", color: "bg-zinc-500/10 text-zinc-400 border-zinc-500/30" },
};

export const QA_STATUS = {
  NOT_REVIEWED: { label: "NOT REVIEWED", color: "bg-zinc-800 text-zinc-400 border-zinc-700" },
  IN_REVIEW: { label: "IN REVIEW", color: "bg-amber-500/10 text-amber-400 border-amber-500/30" },
  PASS: { label: "PASS", color: "bg-emerald-500/10 text-emerald-400 border-emerald-500/30" },
  HOLD: { label: "HOLD", color: "bg-orange-500/10 text-orange-400 border-orange-500/30" },
  FAIL: { label: "FAIL", color: "bg-rose-500/10 text-rose-400 border-rose-500/30" },
};

/**
 * Flagship Character Data Payload: EE-F-002 / Eliska Novak
 * Initial State: v0.8 in VALIDATION status (Using temporary development preview assets)
 */
export const MOCK_ELISKA_CHARACTER = {
  id: "EE-F-002",
  internal_code: "EE-F-002",
  display_name: "ELISKA NOVAK",
  version: "0.8",
  status: "VALIDATION",
  is_locked_production: false,
  
  // Demographics
  gender_presentation: "Female",
  age_range: "22 - 26 yrs",
  ethnicity_anchor: "Eastern European",
  
  // Structured Body Scale & Metrics
  body_metrics: {
    canonical_height_cm: 178,
    stature_class: "Tall",
    body_archetype: "High-Fashion Runway Slim",
    bust_waist_hip: "84 - 60 - 89 cm",
    shoe_size_eu: 39,
    body_profile_status: "Validation / Angle Gate Active",
  },
  
  // Permanent Character DNA
  dna: {
    identity_dna: {
      face_shape: "Oval Architectural",
      eye_color: "Deep Hazel-Green",
      eye_shape: "Almond Upturned",
      nose_bridge: "Refined Straight",
      jawline: "Sculpted Angular",
      cheekbones: "High Defined",
    },
    body_dna: {
      shoulder_width: "Balanced Runway Athletic",
      torso_ratio: "Elongated High-Fashion",
      posture_anchor: "Editorial Erect",
    },
    skin_and_hair: {
      base_skin_tone: "Fair Natural Warm",
      skin_texture_profile: "Fine Pore Natural Matte",
      base_hair_color: "Dark Ash Blonde",
      hair_style_default: "Sleek Straight Center-Part",
    },
    landmarks: {
      left_cheek_mole: "Minor subtle beauty mark (Left Upper Cheek)",
      right_collarbone: "Soft Natural Contour Point",
    }
  },

  // Dynamic Reference Angles (No fixed hardcoding)
  angle_references: {
    identity: [
      { id: "gold_portrait", angle: "GOLDEN PORTRAIT", framing: "Close-Up", url: "/api/placeholder/400/500", status: "VALIDATION" },
      { id: "gold_face", angle: "FACE REFERENCE", framing: "Tight Macro", url: "/api/placeholder/400/500", status: "VALIDATION" },
      { id: "gold_detail", angle: "DETAIL REFERENCE", framing: "Profile Angle", url: "/api/placeholder/400/500", status: "VALIDATION" },
    ],
    half_body: [
      { id: "hb_front", angle: "FRONT", framing: "Half-Body", url: "/api/placeholder/400/500", status: "PASS" },
      { id: "hb_l30", angle: "L30", framing: "Half-Body", url: "/api/placeholder/400/500", status: "PASS" },
      { id: "hb_r30", angle: "R30", framing: "Half-Body", url: "/api/placeholder/400/500", status: "PASS" },
      { id: "hb_l45", angle: "L45", framing: "Half-Body", url: "/api/placeholder/400/500", status: "VALIDATION" },
      { id: "hb_r45", angle: "R45", framing: "Half-Body", url: "/api/placeholder/400/500", status: "VALIDATION" },
    ],
    full_body: [
      { id: "fb_front", angle: "FRONT", framing: "Full-Body", url: "/api/placeholder/400/500", status: "PASS" },
      { id: "fb_l30", angle: "L30", framing: "Full-Body", url: "/api/placeholder/400/500", status: "PASS" },
      { id: "fb_r30", angle: "R30", framing: "Full-Body", url: "/api/placeholder/400/500", status: "PASS" },
      { id: "fb_l45", angle: "L45", framing: "Full-Body", url: "/api/placeholder/400/500", status: "IN_REVIEW" },
      { id: "fb_r45", angle: "R45", framing: "Full-Body", url: "/api/placeholder/400/500", status: "IN_REVIEW" },
    ]
  },

  // QA Status Categories
  qa_matrix: {
    identity_qa: { status: "PASS", reviewer: "Aryan", note: "ArcFace similarity 0.962 - Lock Ready" },
    body_qa: { status: "PASS", reviewer: "Aryan", note: "Proportions & height ratio verified" },
    angle_qa: { status: "IN_REVIEW", reviewer: "Aryan", note: "Full-Body L45/R45 final gate underway" },
    hands_qa: { status: "PASS", reviewer: "Aryan", note: "5-digit anatomy score 98%" },
    feet_qa: { status: "PASS", reviewer: "Aryan", note: "Footwear mesh fit verified" },
    training_eligibility: { status: "PASS", reviewer: "System", note: "Dataset frozen & compliant" },
    production_eligibility: { status: "HOLD", reviewer: "Shahida", note: "Awaiting final V1.0 Lock" },
  }
};
