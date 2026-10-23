# Character Runtime: design and customer API contract

Status: design, for review by Shahida and Indra. No code, migrations or settings change with this
document; the implementation lands as the small PRs in section 8.

Update 2026-10-23: PRs 1–4 of section 8 are built (#55, #57 merged; #59, #60 in review), plus #56
(Rosanne) and #58 (migrations on deploy). Section 10 records where they deviate from this design.
Shahida's Appearance / Styling Capability direction (10 phases) changes parts of sections 2, 3, 5, 6
and 8; section 9 summarises the changes and `APPEARANCE_STATUS.md` holds the schema, routes,
payloads, resolver flow, phase status, blockers and the revised PR order.

## 0. Principles

- **One Eliska.** `EE-F-002`, Eliska Novak, Core **V1.0**, **LOCKED**, 178 cm, High-Fashion / Luxury
  Editorial. Her identity (face, body, the immutable reference assets) is fixed. Styling and art
  direction are variable. There is never a second character for a look: no "Luxury Eliska", no
  "Eliska Evening". A look is a selection of options on top of the one locked core.
- **Character ≠ Appearance.** Character Core = who she is (locked version + identity/body DNA +
  reference assets). Appearance = how she is styled (hair, makeup, expression, jewelry, beauty
  direction), which never edits the core.
- **Strategy-based runtime.** Every generation runs one strategy: `REFERENCE_ONLY` (default: the
  locked reference assets carry identity) or `REFERENCE_PLUS_ADAPTER` (optional, references plus a
  versioned internal adapter). Adapters are internal and versioned; the EE-F-002 750-step adapter
  stays at `EVALUATION` and is never used for customer generations until promoted.
- **Capability Registry pipeline.** Aryan validates → Anshu registers/promotes → the API returns it →
  the frontend displays it. Validation and promotion are per character. Customers only ever receive
  promoted options.
- **Customer responses never contain**: LoRA, adapter, checkpoint, adapter/reference strength,
  seed, CFG, workflow, model provider, ComfyUI, training run (as words, field names or values). The
  UI never offers or implies editing face or body.

## 1. Gap analysis against the current backend

The backend already has most of the building blocks; the gaps are in how they fit the direction
above. File references are to `backend/`.

### 1.1 What exists

| Area | Where | What it does today |
|---|---|---|
| Locked Character Core | `app/models/db.py:1880` `CharacterRegistryVersion` (`character_registry_versions`); `app/services/character_versions.py` | Versions with `status`, `locked`, `canonical_height_cm`, `stature`, `body_archetype`, DNA/QA snapshots. ORM guards reject updates/deletes of a locked row (`db.py:1953-1975`). `seed_ee_f_002_v1` locks EE-F-002 V1.0 at 178 cm, `TALL`, `HIGH_FASHION_RUNWAY_SLIM` (`character_versions.py:31`, `:181`). |
| Character record | `db.py:1862` `CharacterV2` (`characters_v2`); `app/routers/character_registry_v2.py` | `character_id`, `display_name`, `customer_visible`, `production_enabled`. `GET /api/v1/characters-v2/{id}/current-version` is customer-safe (`character_registry_v2.py:574`). |
| Identity / body / appearance DNA | `db.py:1981` `CharacterIdentityDNA`, `:2051` `CharacterBodyDNA`, `:2101` `CharacterAppearanceProfile`, `:2220` `CharacterRuntimeV2` | Detailed face/body descriptors per version; `CharacterRuntimeV2` has `golden_reference_set`, `default_strength`, `approved_workflows`. |
| Reference assets | `db.py:2132` `CanonicalAsset` (`canonical_assets`) | Per-asset role, framing, angles, hash, per-region QA, `production_reference_eligible`, `active_canonical`. |
| Older registry (v1) | `db.py:1165-1261` `CharacterIdentityProfile`, `CharacterBodyProfile`, `CharacterSkinProfile`, `CharacterHairProfile`, `CharacterRuntimeProfile`; `app/routers/character_registry.py` | A parallel, older character registry (string `character_id`, runtime profile with `default_strength`). |
| Brand characters (legacy) | `db.py:257` `Character`, `:313` `CharacterVersion`; `app/routers/brand_characters.py` | Brand-owned characters with LoRA-era `prompt_trigger`, `mlflow_run_id`. Unrelated to EE-F-002. |
| Appearance options | `db.py:1611` `AppearanceOption`; `app/services/appearance_options.py`; `app/routers/styling_options.py` | Categories `HAIR_STYLE`, `MAKEUP_STYLE`, `EXPRESSION`, `NAILS`, `JEWELRY`, `BEAUTY_DIRECTION` (`appearance_options.py:41`). Lifecycle `IN_DEVELOPMENT → VALIDATION → APPROVED → PRODUCTION → ARCHIVED`; validation checks `identity, face, body, capability` must PASS before APPROVED. Customers see only PRODUCTION options of the current locked version via `GET /api/v1/characters/{id}/styling-options`. Seeded defaults: `CANONICAL` hair, `NATURAL` makeup, `NEUTRAL_EDITORIAL` expression (`appearance_options.py:56`). |
| Capability packs | `db.py:1653` `CapabilityPack`, `:1692` `CapabilityPackAdapter`; `app/services/capability_packs.py` | Per character + pack type (GARMENT, FOOTWEAR, BAGS, EYEWEAR, HEADWEAR, JEWELRY), same lifecycle, one PRODUCTION version per pack type, `workflow_route`, `required_reference_assets`, `compatible_poses`. Customer product types `garment, shoes, bags, eyewear, headwear, jewelry` (`capability_packs.py:49`). |
| Poses | `db.py:1726` `PoseDefinition`, `:1752` `PoseProductType`; `app/services/pose_resolver.py`; `GET /api/v1/characters/{id}/poses?product_type=` | 21 seeded poses with categories `static, motion, detail, portrait` and framings `full_body, three_quarter, half_body, close_up, detail` (`pose_resolver.py:33-75`). Offered only when the product type's pack is PRODUCTION. Returned as a flat list. |
| Scene presets | `db.py:1805` `Preset`; `app/services/presets_registry.py`; `GET /api/v1/presets/{locations,lighting,campaigns}` | LOCATION, LIGHTING, CAMPAIGN presets with the same lifecycle; `technical_config` admin-only. |
| Adapter registry | `db.py:1497` `ModelArtifact` (+ `layer`, `kind`, `reference`); `app/services/training_registry.py`; `/api/v1/admin/training/*` | Adapters by layer (`IDENTITY … SCENE`) and kind (`TRAINED_MODEL, WORKFLOW, REFERENCE_SET, CONFIGURATION`). Status default `EXPERIMENTAL`; `promote_run` sets `PRODUCTION` with alias `PROD-<char>-<ver>-<layer>` (`training_registry.py:414-435`). Runs: `PREPARING → TRAINING → EVALUATING → PASSED/FAILED → PROMOTED`. |
| Resolver | `app/services/production_dispatch.py:257` `resolve_runtime_profile` | Turns a dispatch request into a Runtime Character Profile (layers, workflow route, provider route, params) stored admin-only on `productions.runtime_profile`; credits reserved once; customer responses are filtered (`production_dispatch.py:1-19`). |
| Production API | `app/routers/productions.py`; `POST /api/v1/productions/dispatch`, `GET /api/v1/productions/{id}`, `GET /api/v1/admin/productions/{id}` | Editor+ of the product asset's brand dispatches (`production_dispatch.py:117`); reads follow `app/services/job_access.py` (brand members, platform admins). |
| Auth patterns | `app/services/job_access.py`, `app/middleware/auth.py` (`check_brand_role`, `require_platform_admin`) | Reads: brand member (viewer+), else the same 404 as an unknown id. Writes: editor+ (some admin), 403 for too low a role. Platform-admin-only admin APIs. |

### 1.2 Gaps

1. **No generation strategy.** `resolve_runtime_profile` always attaches every `PRODUCTION`
   adapter of the version plus pack/option/pose adapters (`production_dispatch.py:305-322`); there
   is no `REFERENCE_ONLY` default, no explicit `REFERENCE_PLUS_ADAPTER` choice, and reference
   assets are not selected into the plan at all.
2. **No `EVALUATION` adapter state.** Adapters are `EXPERIMENTAL` or `PRODUCTION`
   (`db.py:1510`, `training_registry.py:414`). The EE-F-002 750-step adapter is not registered
   anywhere in code or seeds; it must be registered and pinned at `EVALUATION` so dispatch cannot
   pick it up.
3. **Reference assets are mutable.** `canonical_assets` has no immutability guard (only
   `character_registry_versions` has ORM guards, `db.py:1953`); a file's role/QA/status can change
   after a version is locked, and there is no frozen, hashed reference set per version.
4. **Beauty Direction is a flat option.** `BEAUTY_DIRECTION` is one more `AppearanceOption`
   category; there is no bundle of coordinated defaults (hair, makeup, expression, jewelry, pose
   attitude, lighting), no `recommended_defaults`, no per-piece `overridable` rule and no backend
   validation of overrides. No direction is seeded.
5. **Option shape and ids differ from the agreed contract.** Customer ids are bare lowercase option
   ids (`soft_waves`, `walking`) or registry keys (`ENV-STU-0001`, `ecommerce`); there is no
   category namespace (`hair_*`, `beauty_*`, `campaign_*` …), no `group`, no `recommended`. Two
   categories with the same label (beauty vs campaign "Quiet Luxury") would collide.
6. **Validation/promotion is spread over five lifecycles** (appearance options, capability packs,
   poses, presets, adapters) with per-table `validation` JSON and `status_changed_by`. Poses and
   presets are global, not per character: there is no record that a pose or a lighting preset was
   validated *for EE-F-002*. Validator vs promoter (Aryan vs Anshu) is not recorded separately.
7. **No camera options.** Camera is a raw `focal_length_mm` and `aspect_ratio` on the dispatch
   request (`productions.py:64`, `production_presets.py`); framing is only a pose attribute. There
   are no customer options for shot type (Portrait, Waist Up, 3/4, Full Body, Detail), height,
   angle or lens feel.
8. **Pose groups and product types don't match the UI.** Poses come back flat with technical
   categories; the UI wants groups Recommended, Catalog, Editorial, Motion, Seated,
   Product-Specific. The contract uses `product_type=dress`; the backend has `garment`. Dress lacks
   Front, 3/4 and Hand on Hip; labels differ ("Shoe Detail" vs "Footwear Detail", "Product Detail"
   vs "Bag Detail", "Temple Adjustment" vs "Temple Adjust").
9. **Progress statuses.** `customer_status` maps job states to `queued / processing / completed /
   failed` (`production_dispatch.py:66`); the UI needs `QUEUED, PREPARING, GENERATING, FINALIZING,
   QA, COMPLETE` (+ `FAILED`, `CANCELLED`).
10. **No review loop.** There is no per-output approval, variation, "change one thing and keep the
    rest", export or save-to-campaign on productions. The legacy `POST /api/v1/generate/regenerate`
    only writes an unprocessed row (`app/routers/phase2_batch.py`).
11. **Duplicate character registries.** `characters` (brand LoRA era), `character_registry.py` (v1
    profiles) and `characters_v2` + DNA + `character_registry_versions` (v2) coexist. Dispatch uses
    v2 (`character_versions.get_current_locked_version`). The v1 and brand-character routes are
    not part of the runtime and should be frozen/retired.
12. **Customer leakage outside productions.** `GET /api/v1/rosanne/*` returns `identity_strength`
    (`app/routers/rosanne_pipeline.py:34`) — a strength value in a customer response. Rosanne is
    disabled in production (PR #50) but the response shape must not be reused.
13. **Character entitlement is not modelled.** Characters are platform-global (`customer_visible`);
    nothing says which brands may use EE-F-002 (see open questions).

## 2. Components

```
Customer option ids ──► Option API ──► Resolver/Strategy ──► internal generation plan ──► worker
                           ▲                 ▲   ▲   ▲
        Capability Registry (promoted only)  │   │   └ Adapter Registry (internal, versioned)
        Beauty Direction packs ──────────────┘   └──── Reference Asset Store (immutable)
        Appearance Profile ◄──── Character Core (LOCKED)
```

1. **Character Core** — `characters_v2` + `character_registry_versions` (+ identity/body DNA). One
   row per character; versions are DRAFT → LOCKED and never change once locked (existing guards).
   Customer view: id, name, version, status, height, archetype, editorial positioning.
2. **Reference Asset Store (immutable)** — the files that carry identity (`canonical_assets`) frozen
   into a **reference set** per character version: an ordered list of asset ids with content
   hashes and roles (`face_front`, `face_34`, `body_full`, …). A locked set can never change; a new
   set is a new version. Only sets marked `production` are used by the resolver.
3. **Appearance Profile** — the variable layer: hair, makeup, expression, jewelry options
   (`appearance_options`), plus the canonical defaults of the version. Options never touch the core.
4. **Capability Registry + per-character validation/promotion** — one record per
   (character, version, capability type, capability key, capability version) holding validation
   evidence (Aryan), promotion (Anshu), retirement. Covers every customer-visible option family:
   hair, makeup, expression, jewelry, beauty direction, pose, camera, scene, lighting, campaign, and
   product types (capability packs). The Option API returns only `PROMOTED` records.
5. **Beauty Direction packs** — versioned bundles (`QUIET_LUXURY_V1`) with `recommended_defaults`
   for hair, makeup, expression, jewelry, pose attitude and lighting, plus which pieces are
   overridable. Each referenced default must itself be promoted for the character.
6. **Adapter Registry (internal)** — `model_artifacts` adapters (existing), with an `EVALUATION`
   state and strategy eligibility. Never visible to customers.
7. **Resolver / Strategy** — turns customer option ids into an internal generation plan: strategy,
   reference set, adapter (only for `REFERENCE_PLUS_ADAPTER` and only a `PRODUCTION` adapter),
   resolved appearance/pose/camera/scene parameters, workflow and provider route, params. Extends
   `production_dispatch.resolve_runtime_profile`; the plan stays admin-only on `productions`.
8. **Customer-facing Option API** — read-only, brand-authenticated endpoints that list promoted
   options in the agreed shape, plus the production (generate / progress / review) endpoints.

### 2.1 Strategy rules

| | `REFERENCE_ONLY` (default) | `REFERENCE_PLUS_ADAPTER` |
|---|---|---|
| Identity carried by | the version's production reference set | reference set + one promoted IDENTITY adapter |
| When chosen | always, unless the character's runtime enables the adapter strategy for the selected capability | only if `allowed_strategies` contains it **and** a `PRODUCTION` adapter exists for the version and layer |
| Adapter states usable | none | `PRODUCTION` only (never `EXPERIMENTAL`, `EVALUATION`, `ARCHIVED`) |
| Customer can choose? | no | no — internal decision, recorded on the plan |

For EE-F-002 V1.0: `default_strategy = REFERENCE_ONLY`, `allowed_strategies = [REFERENCE_ONLY]`
until the 750-step adapter passes evaluation and is promoted.

### 2.2 Override rules (Beauty Direction)

1. The request names a `beauty_direction_id` (optional). Its `recommended_defaults` fill every piece
   the request leaves empty.
2. A piece the request sets explicitly wins **only if** the direction lists it as `overridable` and
   the option is promoted for the character; otherwise 422 naming the field.
3. Non-overridable pieces (e.g. `lighting_id` for a direction that fixes lighting) are rejected when
   they differ from the default.
4. The resolved selection (after defaults and overrides) is stored on the production, so a
   variation can change one piece and keep the rest.

## 3. Data model and migration plan

Design only; each change is an add-if-missing Alembic revision (pattern of
`alembic/versions/schema_drift_001.py`) in the PR that needs it. Nothing existing is dropped.

### 3.1 New tables

**`character_reference_sets`** — immutable reference sets.

| column | type | notes |
|---|---|---|
| id | int PK | |
| reference_set_id | varchar(60) unique | e.g. `EE-F-002_V1.0_REF_V1` |
| character_id | varchar(50) | index |
| character_version | varchar(10) | |
| version | int | per character version |
| status | varchar(20) | `DRAFT → LOCKED → PRODUCTION → RETIRED` |
| locked_at, locked_by | timestamp, varchar | |
| content_hash | char(64) | sha256 over ordered (asset_id, sha256) |
| created_at | timestamp | |

Unique (character_id, character_version, version); partial unique index: one `PRODUCTION` set per
(character_id, character_version). ORM guards like `character_registry_versions`: no update of a
LOCKED/PRODUCTION row except `status` forward, no delete.

**`character_reference_set_items`** — (reference_set_id FK, canonical_asset_id FK, role varchar(30),
sort_order int, content_hash_sha256 char(64) copied at lock time). Unique (reference_set_id, role,
sort_order). Immutable once the set is locked (guard + the hash check at resolve time).

**`capability_validations`** — the per-character registry record.

| column | type | notes |
|---|---|---|
| id | int PK | |
| character_id, character_version | varchar | index |
| capability_type | varchar(30) | `HAIR, MAKEUP, EXPRESSION, JEWELRY, BEAUTY_DIRECTION, POSE, CAMERA, SCENE, LIGHTING, CAMPAIGN, PRODUCT_TYPE` |
| capability_key | varchar(80) | internal key, e.g. `QUIET_LUXURY`, `hand_on_hip`, `ENV-STU-0001` |
| capability_version | int | |
| customer_id | varchar(80) | namespaced id returned to customers, e.g. `beauty_quiet_luxury` |
| status | varchar(20) | `REGISTERED → VALIDATING → VALIDATED → PROMOTED → RETIRED` (+ `REJECTED`) |
| validation | jsonb | checks and evidence (identity/face/body/product, sample output ids, notes) |
| validated_by, validated_at | varchar, timestamp | Aryan |
| promoted_by, promoted_at | varchar, timestamp | Anshu |
| retired_by, retired_at, retire_reason | | |
| is_default, recommended | bool | per character |
| group | varchar(30) | UI group (pose groups, camera groups, scene groups) |
| sort_order | int | |
| created_at, updated_at | | |

Unique (character_id, character_version, capability_type, capability_key, capability_version);
unique (character_id, character_version, customer_id) among non-retired rows (partial index); index
(character_id, character_version, capability_type, status). Customers see `PROMOTED` only.

The existing per-table lifecycles stay as the definition store (what a pose/preset/option *is*);
`capability_validations` records whether it is validated and promoted *for this character*. PR 3
backfills a `PROMOTED` row for every option already in `PRODUCTION` today so nothing disappears.

**`beauty_directions`** — versioned bundles. *Superseded (section 9): a beauty direction stays an
`appearance_options` row of category `BEAUTY_DIRECTION`; `beauty_directions` becomes a 1:1 extension
holding only the recommended hair/makeup/expression/grooming option ids.*

| column | type | notes |
|---|---|---|
| id | int PK | |
| direction_key | varchar(40) | `QUIET_LUXURY` |
| version | int | |
| internal_key | varchar(60) unique | `QUIET_LUXURY_V1` |
| customer_id | varchar(60) | `beauty_quiet_luxury` (stable across versions) |
| label, description, thumbnail_url | | |
| recommended_defaults | jsonb | `{hair_id, makeup_id, expression_id, jewelry_id, pose_attitude_id, lighting_id}` (customer ids) |
| overridable | jsonb | list of keys of `recommended_defaults` the customer may change |
| status | varchar(20) | same lifecycle as appearance options |
| created_by, created_at, updated_at | | |

Unique (direction_key, version); one PRODUCTION version per direction_key (partial unique).
Per-character availability is a `capability_validations` row (type `BEAUTY_DIRECTION`).

**`production_outputs`** — reviewable outputs.

| column | type | notes |
|---|---|---|
| id | int PK | |
| output_id | varchar(40) unique | `out_<hex>` |
| production_id | FK productions.production_id | index |
| index | int | 0..count-1 |
| asset_id | FK assets.id | the stored image (brand asset) |
| review_status | varchar(20) | `PENDING_REVIEW, APPROVED, REJECTED` |
| reviewed_by, reviewed_at | | |
| campaign_id | FK campaigns.id null | after Save to Campaign |
| created_at | | |

### 3.2 Column additions

| table | columns | why |
|---|---|---|
| `characters_v2` | `positioning varchar(80)` (High-Fashion / Luxury Editorial), `entitled_brand_ids jsonb null` (see open questions) | profile, entitlement |
| `character_runtime_v2` | ~~`default_strategy varchar(30) default 'REFERENCE_ONLY'`, `allowed_strategies jsonb`, `reference_set_id varchar(60)`~~ *superseded: a new versioned `runtime_profiles` table (section 9)* | strategy |
| `model_artifacts` | status vocabulary gains `EVALUATION` (no schema change; service + CHECK in code), ~~`strategy_eligible bool default false`~~ *dropped (section 9)* | adapter gate |
| `appearance_options` | ~~`customer_id varchar(80)`, `group varchar(30)`, `recommended bool default false`~~ *not added: these live on `capability_validations` (#59, section 10)* | contract shape |
| `pose_definitions` | ~~`customer_id varchar(80)` (`pose_<pose_id>`)~~ *(on `capability_validations`, #59)*, `attitude varchar(30)` | ids, beauty direction "pose attitude" |
| `pose_product_types` | `group varchar(30)` | Recommended / Catalog / Editorial / Motion / Seated / Product-Specific |
| `presets` | ~~`customer_id varchar(80)`, `group varchar(30)`~~ *(on `capability_validations`, #59)*; `preset_type` gains `CAMERA_SHOT, CAMERA_HEIGHT, CAMERA_ANGLE, LENS` | camera + scene groups |
| `capability_product_types` | `aliases jsonb` (e.g. `dress → garment`) | `product_type=dress` |
| `productions` | `strategy varchar(30)`, `selection jsonb` (resolved customer ids), `stage varchar(20)`, `parent_production_id varchar(40) null`, `variation_of_output_id varchar(40) null`, `kept jsonb` | progress, variations |

All new columns are nullable or defaulted, so migrations are additive, add-if-missing and safe on
production. `customer_id` columns are backfilled deterministically from existing keys
(`hair_` + lower(option_id), `pose_` + pose_id, `scene_` / `lighting_` / `campaign_` + lower key).

### 3.3 Versioning

- Character Core: `character_registry_versions` (DRAFT → LOCKED, immutable).
- Reference set: per character version, `REF_V<n>`; a new set never changes an old one.
- Options, poses, presets, beauty directions: `version` per key; customer ids are stable across
  versions; one PRODUCTION version per key; the production stores the internal versions it used.
- Adapters: `model_artifacts` versions (`version_major/minor`), alias moves on promotion.
- Plan: `productions.runtime_profile.profile_version` bumps to 2 when `strategy` and `reference_set`
  are added.

## 4. Customer-facing API contract

All endpoints need a logged-in user (`Authorization: Bearer <token>`), are under `/api/v1`, and
never return the forbidden terms (section 0). Character reads are available to every brand member
of an entitled brand (open question 2; today: every authenticated user). Production writes need
**editor+** of the brand (`check_brand_role`), reads need **viewer+** (`job_access.require_readable`);
another brand's production or an unknown id is the same `404`, a member below the role `403`.

**Option object (every list below):**

```json
{ "id": "hair_sleek_low_bun", "label": "Sleek Low Bun", "thumbnail_url": "/presets/hair/sleek-low-bun.jpg",
  "group": "Polished", "is_default": false, "recommended": true }
```

IDs are namespaced by category: `hair_*`, `makeup_*`, `expr_*`, `jewelry_*`, `beauty_*`, `pose_*`,
`camera_*`, `scene_*`, `lighting_*`, `campaign_*`. Labels may repeat across categories
(`beauty_quiet_luxury` vs `campaign_quiet_luxury`).

### 4.1 Character profile

`GET /api/v1/characters/EE-F-002/profile`

```json
{
  "id": "EE-F-002",
  "name": "Eliska Novak",
  "version": "1.0",
  "status": "LOCKED",
  "height_cm": 178,
  "positioning": "High-Fashion / Luxury Editorial",
  "thumbnail_url": "/characters/ee-f-002/cover.jpg",
  "product_types": [
    { "id": "dress", "label": "Dress", "thumbnail_url": "/presets/product/dress.jpg", "group": "Apparel",
      "is_default": true, "recommended": true },
    { "id": "shoes", "label": "Shoes", "thumbnail_url": "/presets/product/shoes.jpg", "group": "Accessories",
      "is_default": false, "recommended": false }
  ]
}
```

`404` for an unknown or unreleased character (same message).

### 4.2 Style options

`GET /api/v1/characters/EE-F-002/style-options`

```json
{
  "character_id": "EE-F-002",
  "hair": [
    { "id": "hair_canonical_straight", "label": "Canonical Straight", "thumbnail_url": "/presets/hair/canonical-straight.jpg",
      "group": "Signature", "is_default": true, "recommended": true },
    { "id": "hair_sleek_low_bun", "label": "Sleek Low Bun", "thumbnail_url": "/presets/hair/sleek-low-bun.jpg",
      "group": "Polished", "is_default": false, "recommended": true }
  ],
  "makeup": [
    { "id": "makeup_natural_minimal", "label": "Natural Minimal", "thumbnail_url": "/presets/makeup/natural-minimal.jpg",
      "group": "Signature", "is_default": true, "recommended": true },
    { "id": "makeup_luminous_nude", "label": "Luminous Nude", "thumbnail_url": "/presets/makeup/luminous-nude.jpg",
      "group": "Soft", "is_default": false, "recommended": true }
  ],
  "expression": [
    { "id": "expr_neutral_editorial", "label": "Neutral Editorial", "thumbnail_url": "/presets/expression/neutral-editorial.jpg",
      "group": "Editorial", "is_default": true, "recommended": true },
    { "id": "expr_soft_confidence", "label": "Soft Confidence", "thumbnail_url": "/presets/expression/soft-confidence.jpg",
      "group": "Warm", "is_default": false, "recommended": false }
  ],
  "jewelry": [
    { "id": "jewelry_none", "label": "None", "thumbnail_url": "/presets/jewelry/none.jpg",
      "group": "None", "is_default": true, "recommended": false },
    { "id": "jewelry_minimal_gold", "label": "Minimal Gold", "thumbnail_url": "/presets/jewelry/minimal-gold.jpg",
      "group": "Fine", "is_default": false, "recommended": true }
  ]
}
```

Replaces `GET /api/v1/characters/{id}/styling-options` (kept as an alias until the frontend moves).

### 4.3 Beauty directions

`GET /api/v1/characters/EE-F-002/beauty-directions`

```json
{
  "character_id": "EE-F-002",
  "beauty_directions": [
    {
      "id": "beauty_quiet_luxury",
      "label": "Quiet Luxury",
      "thumbnail_url": "/presets/beauty/quiet-luxury.jpg",
      "group": "Luxury",
      "is_default": true,
      "recommended": true,
      "recommended_defaults": {
        "hair_id": "hair_sleek_low_bun",
        "makeup_id": "makeup_luminous_nude",
        "expression_id": "expr_soft_confidence",
        "jewelry_id": "jewelry_minimal_gold",
        "pose_attitude_id": "pose_attitude_poised",
        "lighting_id": "lighting_soft_window"
      },
      "overridable": ["hair_id", "makeup_id", "expression_id", "jewelry_id"]
    }
  ]
}
```

The six directions (Quiet Luxury, European Editorial, Soft Luxury, Classic Evening, Modern Minimal,
Resort Luxury) are returned only once promoted for the character. Every id inside
`recommended_defaults` is itself a promoted option for this character (validated on promotion).

### 4.4 Poses by product type

`GET /api/v1/characters/EE-F-002/poses?product_type=dress`

```json
{
  "character_id": "EE-F-002",
  "product_type": "dress",
  "groups": [
    { "group": "Recommended", "poses": [
      { "id": "pose_front", "label": "Front", "thumbnail_url": "/presets/pose/front.jpg", "group": "Recommended",
        "is_default": true, "recommended": true },
      { "id": "pose_three_quarter", "label": "3/4", "thumbnail_url": "/presets/pose/three-quarter.jpg", "group": "Recommended",
        "is_default": false, "recommended": true } ] },
    { "group": "Catalog", "poses": [
      { "id": "pose_hand_on_hip", "label": "Hand on Hip", "thumbnail_url": "/presets/pose/hand-on-hip.jpg", "group": "Catalog",
        "is_default": false, "recommended": false } ] },
    { "group": "Editorial", "poses": [
      { "id": "pose_editorial", "label": "Editorial", "thumbnail_url": "/presets/pose/editorial.jpg", "group": "Editorial",
        "is_default": false, "recommended": false } ] },
    { "group": "Motion", "poses": [
      { "id": "pose_walking", "label": "Walking", "thumbnail_url": "/presets/pose/walking.jpg", "group": "Motion",
        "is_default": false, "recommended": false } ] },
    { "group": "Seated", "poses": [
      { "id": "pose_seated", "label": "Seated", "thumbnail_url": "/presets/pose/seated.jpg", "group": "Seated",
        "is_default": false, "recommended": false } ] },
    { "group": "Product-Specific", "poses": [] }
  ]
}
```

Pose catalogue per product type (labels are the customer labels):

| product_type | poses |
|---|---|
| dress | Front, 3/4, Walking, Hand on Hip, Seated, Editorial |
| shoes | Foot Forward, Profile, Walking, Footwear Detail |
| bag | Hand Carry, Shoulder, Crossbody, Walking, Bag Detail |
| eyewear | Portrait, 30°, 45°, Profile, Temple Adjust |
| jewelry | Portrait, Ear Detail, Neck Detail, Wrist Detail, Hand Detail |

Empty groups are returned so the UI can render a stable tab bar. `422` for an unknown product type
(listing the known ones); a product type whose capability is not promoted returns
`{"groups": []}` with `available: false` (open question 6).

### 4.5 Camera options

`GET /api/v1/characters/EE-F-002/camera-options?product_type=dress`

```json
{
  "character_id": "EE-F-002",
  "shot": [
    { "id": "camera_portrait", "label": "Portrait", "thumbnail_url": "/presets/camera/portrait.jpg", "group": "Shot", "is_default": false, "recommended": false },
    { "id": "camera_waist_up", "label": "Waist Up", "thumbnail_url": "/presets/camera/waist-up.jpg", "group": "Shot", "is_default": false, "recommended": false },
    { "id": "camera_three_quarter", "label": "3/4", "thumbnail_url": "/presets/camera/three-quarter.jpg", "group": "Shot", "is_default": false, "recommended": true },
    { "id": "camera_full_body", "label": "Full Body", "thumbnail_url": "/presets/camera/full-body.jpg", "group": "Shot", "is_default": true, "recommended": true },
    { "id": "camera_detail", "label": "Detail", "thumbnail_url": "/presets/camera/detail.jpg", "group": "Shot", "is_default": false, "recommended": false }
  ],
  "height": [
    { "id": "camera_height_eye", "label": "Eye Level", "thumbnail_url": "/presets/camera/height-eye.jpg", "group": "Height", "is_default": true, "recommended": true },
    { "id": "camera_height_low", "label": "Low", "thumbnail_url": "/presets/camera/height-low.jpg", "group": "Height", "is_default": false, "recommended": false }
  ],
  "angle": [
    { "id": "camera_angle_front", "label": "Front", "thumbnail_url": "/presets/camera/angle-front.jpg", "group": "Angle", "is_default": true, "recommended": true },
    { "id": "camera_angle_side", "label": "Side", "thumbnail_url": "/presets/camera/angle-side.jpg", "group": "Angle", "is_default": false, "recommended": false }
  ],
  "lens": [
    { "id": "camera_lens_editorial_85", "label": "Editorial Portrait", "thumbnail_url": "/presets/camera/lens-85.jpg", "group": "Lens Feel", "is_default": true, "recommended": true },
    { "id": "camera_lens_wide_35", "label": "Wide Environmental", "thumbnail_url": "/presets/camera/lens-35.jpg", "group": "Lens Feel", "is_default": false, "recommended": false }
  ]
}
```

Shots that a product type's framing rules forbid (e.g. eyewear needs the face) are not returned
for that product type (existing `capability_product_types.required_framings`).

### 4.6 Scene, lighting and campaign options

`GET /api/v1/characters/EE-F-002/scene-options`

```json
{
  "character_id": "EE-F-002",
  "scene": [
    { "id": "scene_studio_white", "label": "White Studio", "thumbnail_url": "/presets/scene/studio-white.jpg", "group": "Studio", "is_default": true, "recommended": true },
    { "id": "scene_parisian_salon", "label": "Parisian Salon", "thumbnail_url": "/presets/scene/parisian-salon.jpg", "group": "Interior", "is_default": false, "recommended": true },
    { "id": "scene_riviera_terrace", "label": "Riviera Terrace", "thumbnail_url": "/presets/scene/riviera-terrace.jpg", "group": "Exterior", "is_default": false, "recommended": false },
    { "id": "scene_milan_street", "label": "Milan Street", "thumbnail_url": "/presets/scene/milan-street.jpg", "group": "Location", "is_default": false, "recommended": false }
  ],
  "lighting": [
    { "id": "lighting_soft_window", "label": "Soft Window", "thumbnail_url": "/presets/lighting/soft-window.jpg", "group": "Natural", "is_default": true, "recommended": true },
    { "id": "lighting_evening_glow", "label": "Evening Glow", "thumbnail_url": "/presets/lighting/evening-glow.jpg", "group": "Dramatic", "is_default": false, "recommended": false }
  ]
}
```

`GET /api/v1/characters/EE-F-002/campaign-options`

```json
{
  "character_id": "EE-F-002",
  "campaign": [
    { "id": "campaign_ecommerce", "label": "E-commerce", "thumbnail_url": "/presets/campaign/ecommerce.jpg", "group": "Commerce", "is_default": true, "recommended": true },
    { "id": "campaign_quiet_luxury", "label": "Quiet Luxury", "thumbnail_url": "/presets/campaign/quiet-luxury.jpg", "group": "Editorial", "is_default": false, "recommended": true }
  ],
  "output": {
    "aspect_ratios": ["1:1", "3:4", "4:5", "2:3", "9:16", "16:9"],
    "count": { "min": 1, "max": 8, "default": 4 },
    "quality": [ { "id": "quality_high_fidelity", "label": "High Fidelity", "is_default": true },
                 { "id": "quality_fast_preview", "label": "Fast Preview", "is_default": false } ],
    "resolutions": ["1K", "2K", "4K"]
  }
}
```

Output values mirror `app/services/production_presets.py`.

### 4.7 Generate

`POST /api/v1/productions` — editor+ of `brand_id`; `Idempotency-Key` header supported (as dispatch).

```json
{
  "brand_id": 12,
  "character_id": "EE-F-002",
  "product": { "product_type": "dress", "asset_id": 1042 },
  "style": {
    "beauty_direction_id": "beauty_quiet_luxury",
    "hair_id": "hair_canonical_straight",
    "makeup_id": null,
    "expression_id": null,
    "jewelry_id": null
  },
  "pose_id": "pose_three_quarter",
  "camera": { "shot_id": "camera_three_quarter", "height_id": "camera_height_eye", "angle_id": "camera_angle_front",
              "lens_id": "camera_lens_editorial_85" },
  "scene": { "scene_id": "scene_parisian_salon", "lighting_id": null },
  "campaign_id": "campaign_quiet_luxury",
  "output": { "aspect_ratio": "4:5", "count": 4, "quality_id": "quality_high_fidelity", "resolution": "2K" }
}
```

Only option ids; `null` means "use the beauty direction / character default". The backend validates
every id is promoted for the character (422 naming the field otherwise), applies
`recommended_defaults` and override rules (section 2.2), checks the asset belongs to the brand and
the brand's credits.

`202 Accepted`

```json
{
  "production_id": "prd_7f3a9c1e2b",
  "status": "QUEUED",
  "estimated_credits": 16,
  "selection": {
    "beauty_direction_id": "beauty_quiet_luxury",
    "hair_id": "hair_canonical_straight",
    "makeup_id": "makeup_luminous_nude",
    "expression_id": "expr_soft_confidence",
    "jewelry_id": "jewelry_minimal_gold",
    "pose_id": "pose_three_quarter",
    "camera": { "shot_id": "camera_three_quarter", "height_id": "camera_height_eye", "angle_id": "camera_angle_front",
                "lens_id": "camera_lens_editorial_85" },
    "scene_id": "scene_parisian_salon",
    "lighting_id": "lighting_soft_window",
    "campaign_id": "campaign_quiet_luxury"
  },
  "created_at": "2026-10-20T10:12:00Z"
}
```

Errors: `402` (credits, nothing charged), `403` (role), `404` (unknown character or another brand's
asset — same message), `409` (idempotency key reused with a different body), `422` (field, with
`loc` naming it), `503` (studio disabled / capability temporarily unavailable, nothing charged).

### 4.8 Progress

`GET /api/v1/productions/prd_7f3a9c1e2b` — viewer+ of the production's brand.

```json
{
  "production_id": "prd_7f3a9c1e2b",
  "status": "GENERATING",
  "progress": { "stage": "GENERATING", "percent": 45,
                "stages": ["QUEUED", "PREPARING", "GENERATING", "FINALIZING", "QA", "COMPLETE"] },
  "selection": { "...": "as in the generate response" },
  "outputs": [],
  "credits_charged": 0,
  "created_at": "2026-10-20T10:12:00Z"
}
```

Statuses: `QUEUED → PREPARING → GENERATING → FINALIZING → QA → COMPLETE`; terminal `FAILED`
(credits refunded once, PR #45 helper) and `CANCELLED`. Live updates on the existing
`WS /api/v1/ws/generation/{production_id}/progress?token=…&brand_id=…` (PR #51 rules), events
`{"event": "generation.progress", "stage": "QA", "percent": 90}`.

### 4.9 Result and review actions

`GET /api/v1/productions/prd_7f3a9c1e2b` when complete:

```json
{
  "production_id": "prd_7f3a9c1e2b",
  "status": "COMPLETE",
  "progress": { "stage": "COMPLETE", "percent": 100 },
  "selection": { "...": "..." },
  "outputs": [
    { "output_id": "out_01a2", "index": 0, "image_url": "https://cdn.modelens.ai/brands/12/prd_7f3a9c1e2b/0.jpg",
      "thumbnail_url": "https://cdn.modelens.ai/brands/12/prd_7f3a9c1e2b/0_thumb.jpg", "review_status": "PENDING_REVIEW",
      "actions": ["approve", "create_variation", "change_hair", "change_makeup", "change_pose", "change_location",
                  "regenerate", "download", "save_to_campaign"] }
  ],
  "credits_charged": 16,
  "parent_production_id": null
}
```

Review actions (editor+ unless noted):

| Action | Endpoint | Body | Result |
|---|---|---|---|
| Approve | `POST /api/v1/productions/{id}/outputs/{output_id}/approve` | `{}` | `{"output_id": "out_01a2", "review_status": "APPROVED"}` |
| Create Variation | `POST /api/v1/productions/{id}/variations` | `{"from_output_id": "out_01a2", "changes": {}, "count": 2}` | new production (202, as 4.7) with `parent_production_id`, same selection |
| Change Hair / Makeup / Pose / Location | `POST /api/v1/productions/{id}/variations` | `{"from_output_id": "out_01a2", "changes": {"hair_id": "hair_soft_waves"}}` (or `makeup_id`, `pose_id`, `scene_id`) | new production; every element not in `changes` is kept from the source selection |
| Regenerate | `POST /api/v1/productions/{id}/regenerate` | `{"output_ids": ["out_01a2"]}` | new production, same selection, new run |
| Download / Export | `GET /api/v1/productions/{id}/outputs/{output_id}/download` (viewer+) · `POST /api/v1/productions/{id}/export` `{"output_ids": [...], "format": "zip"}` | | file / `{"export_url": "..."}` |
| Save to Campaign | `POST /api/v1/productions/{id}/outputs/{output_id}/save-to-campaign` | `{"campaign_id": 77}` | `{"output_id": "out_01a2", "campaign_id": 77}` (campaign must be of the same brand, else 404) |

Variation example:

```json
POST /api/v1/productions/prd_7f3a9c1e2b/variations
{ "from_output_id": "out_01a2", "changes": { "hair_id": "hair_soft_waves" }, "count": 2 }

202
{ "production_id": "prd_9b11d0c4aa", "status": "QUEUED", "parent_production_id": "prd_7f3a9c1e2b",
  "kept": ["beauty_direction_id", "makeup_id", "expression_id", "jewelry_id", "pose_id", "camera", "scene_id",
           "lighting_id", "campaign_id"],
  "changed": ["hair_id"], "estimated_credits": 8 }
```

Approved outputs are never modified or regenerated in place; a change always creates a child
production, so approved elements stay as approved. A change that would violate the beauty
direction's override rules is a 422 like on generate.

## 5. Admin / internal API (platform admins only)

All under `/api/v1/admin`, `require_platform_admin` (`users.role` admin/owner); everyone else 403.
They return the internal fields (keys, versions, adapters, evidence). Existing admin APIs stay:
`/admin/appearance/options`, `/admin/capability-packs`, `/admin/poses`, `/admin/presets`,
`/admin/training/*` (definitions); the new ones manage per-character validation and promotion.

| Step | Who | Endpoint |
|---|---|---|
| Register | Anshu | `POST /api/v1/admin/characters/{character_id}/capabilities` |
| Validate | Aryan | `POST /api/v1/admin/characters/{character_id}/capabilities/{capability_type}/{capability_key}/validation` |
| Promote | Anshu | `POST /api/v1/admin/characters/{character_id}/capabilities/{capability_type}/{capability_key}/promote` |
| Retire | Anshu | `POST /api/v1/admin/characters/{character_id}/capabilities/{capability_type}/{capability_key}/retire` |
| List | both | `GET /api/v1/admin/characters/{character_id}/capabilities?type=&status=` |

Register:

```json
POST /api/v1/admin/characters/EE-F-002/capabilities
{ "character_version": "1.0", "capability_type": "BEAUTY_DIRECTION", "capability_key": "QUIET_LUXURY",
  "capability_version": 1, "customer_id": "beauty_quiet_luxury", "group": "Luxury", "sort_order": 10 }

201
{ "character_id": "EE-F-002", "character_version": "1.0", "capability_type": "BEAUTY_DIRECTION",
  "capability_key": "QUIET_LUXURY", "capability_version": 1, "customer_id": "beauty_quiet_luxury",
  "status": "REGISTERED" }
```

Validate (moves to `VALIDATED` when every check passes, `REJECTED` otherwise):

```json
POST .../BEAUTY_DIRECTION/QUIET_LUXURY/validation
{ "capability_version": 1,
  "checks": { "identity": "PASS", "face": "PASS", "body": "PASS", "product": "PASS" },
  "evidence": { "sample_production_ids": ["prd_val_001", "prd_val_002"], "notes": "Identity stable across 24 samples." } }

200
{ "status": "VALIDATED", "validated_by": "aryan@modelens.ai", "validated_at": "2026-10-21T09:00:00Z" }
```

Promote (only from `VALIDATED`; for a beauty direction also checks that every id in its
`recommended_defaults` is promoted for the character; demotes the previously promoted version of
the same key):

```json
POST .../BEAUTY_DIRECTION/QUIET_LUXURY/promote
{ "capability_version": 1, "is_default": true, "recommended": true }

200
{ "status": "PROMOTED", "promoted_by": "anshu@modelens.ai", "promoted_at": "2026-10-21T10:00:00Z",
  "replaced_version": null }
```

Retire:

```json
POST .../POSE/hand_on_hip/retire
{ "capability_version": 1, "reason": "Hand artefacts at 4K." }

200
{ "status": "RETIRED", "retired_by": "anshu@modelens.ai" }
```

Beauty Direction definitions and reference sets:

- `POST /api/v1/admin/beauty-directions` — `{direction_key, label, thumbnail_url, recommended_defaults, overridable}` → creates `QUIET_LUXURY_V1` (IN_DEVELOPMENT); `PATCH` while not live; `POST /{internal_key}/status` for the lifecycle.
- `POST /api/v1/admin/characters/{id}/reference-sets` — `{character_version, items: [{canonical_asset_id, role}]}`; `POST /{reference_set_id}/lock`; `POST /{reference_set_id}/promote`. Locked sets are immutable (409 on change).
- `POST /api/v1/admin/characters/{id}/runtime/strategy` — `{default_strategy, allowed_strategies}`; `REFERENCE_PLUS_ADAPTER` is rejected unless a PRODUCTION adapter exists for the version.
- Adapters: existing `/api/v1/admin/training/adapters`; new `POST /{adapter_id}/status` with `EVALUATION` (and promotion only through `promote_run`).

Every admin write is audit-logged (`app/services/audit_service.py`) with actor and before/after.
*As built (#57, #60): `app/services/audit.write_audit_log`, in the same transaction as the change.*

## 6. EE-F-002 seed record

```json
{
  "character": { "character_id": "EE-F-002", "display_name": "Eliska Novak", "positioning": "High-Fashion / Luxury Editorial",
                 "customer_visible": true, "production_enabled": true },
  "core_version": { "version": "1.0", "status": "LOCKED", "locked": true, "canonical_height_cm": 178.0,
                    "stature": "TALL", "body_archetype": "HIGH_FASHION_RUNWAY_SLIM",
                    "release_notes": "EE-F-002 Eliska Novak V1.0 Character Core lock." },
  "runtime": { "default_strategy": "REFERENCE_ONLY", "allowed_strategies": ["REFERENCE_ONLY"],
               "reference_set_id": "EE-F-002_V1.0_REF_V1" },
  "reference_set": { "reference_set_id": "EE-F-002_V1.0_REF_V1", "status": "PRODUCTION",
                     "items": "the production_reference_eligible canonical assets of V1.0 (face front, face 3/4, profile, full body front, full body 3/4)" },
  "adapters": [ { "adapter_id": "EE-F-002-IDENTITY-750", "layer": "IDENTITY", "kind": "TRAINED_MODEL", "training_steps": 750,
                  "status": "EVALUATION", "strategy_eligible": false } ],
  "appearance_defaults": { "hair": "hair_canonical_straight", "makeup": "makeup_natural_minimal",
                           "expression": "expr_neutral_editorial", "jewelry": "jewelry_none" },
  "beauty_directions": [
    { "internal_key": "QUIET_LUXURY_V1", "customer_id": "beauty_quiet_luxury", "label": "Quiet Luxury" },
    { "internal_key": "EUROPEAN_EDITORIAL_V1", "customer_id": "beauty_european_editorial", "label": "European Editorial" },
    { "internal_key": "SOFT_LUXURY_V1", "customer_id": "beauty_soft_luxury", "label": "Soft Luxury" },
    { "internal_key": "CLASSIC_EVENING_V1", "customer_id": "beauty_classic_evening", "label": "Classic Evening" },
    { "internal_key": "MODERN_MINIMAL_V1", "customer_id": "beauty_modern_minimal", "label": "Modern Minimal" },
    { "internal_key": "RESORT_LUXURY_V1", "customer_id": "beauty_resort_luxury", "label": "Resort Luxury" }
  ],
  "capability_status": "Seeded as IN_DEVELOPMENT / REGISTERED. Only the V1.0 canonical defaults are seeded PROMOTED (they are part of the core lock, as today); every beauty direction, extra style, pose, camera and scene option goes through validate → promote."
}
```

The seed is idempotent and never changes a locked row (as `seed_ee_f_002_v1` and
`seed_ee_f_002_defaults` today). The adapter id above is a placeholder until the real artifact path
and checksum are registered.

*Changed since:*
- The reference set is built and **LOCKED** by the admin seed action and never auto-promoted to
  PRODUCTION (#60).
- The adapter is `EE-F-002_CK0750`. When used, it runs at strength 0.4 with a 0.6 fallback, taken
  from the runtime profile and capability records (section 9).
- The beauty directions are `CANONICAL_CONTROL`, `QUIET_LUXURY`, `LUXURY_WAVES`,
  `RUNWAY_EDITORIAL`, `CLASSIC_EVENING` and `MODERN_MINIMAL` (section 9).
- The canonical defaults have the customer ids `hair_canonical`, `makeup_natural` and
  `expr_neutral_editorial` (#59).

## 7. Open questions

1. **Beauty Direction list mismatch.** *Resolved 2026-10-23 by Shahida's direction: `CANONICAL_CONTROL`,
   `QUIET_LUXURY`, `LUXURY_WAVES`, `RUNWAY_EDITORIAL`, `CLASSIC_EVENING`, `MODERN_MINIMAL` (section 9).*
   Agreed set: Quiet Luxury, European Editorial, Soft Luxury,
   Classic Evening, Modern Minimal, Resort Luxury. Shahida's frontend mail lists Clean, Polished,
   Bronzed, Editorial, After Dark, Resort. Which list ships, and are the frontend names labels for
   the same packs or different packs?
2. **Entitlement.** Can every brand use EE-F-002, or only entitled brands? (Today every
   authenticated user can read `customer_visible` characters.)
3. **`dress` vs `garment`.** The contract uses `product_type=dress`; the backend uses `garment` for all
   apparel. Is `dress` an alias of `garment`, or should apparel split (dress, top, outerwear …) with
   their own pose sets?
4. **Product type ids.** Contract says `BAG`; backend uses `bags`. Singular or plural ids?
5. **Pose attitude and lighting in a beauty direction.** Are they overridable? Does a direction fix
   lighting, or only recommend it? Is "pose attitude" a pose filter or a modifier on any pose?
6. **Unavailable product types.** Should the pose/camera endpoints return 404/503 or an empty list
   with `available: false` when a product type isn't promoted for the character?
7. **Four-eyes rule.** Must the promoter differ from the validator (Anshu ≠ Aryan), or may one
   platform admin do both?
8. **Credits for review actions.** Are variations and regenerations charged like a new production,
   at a discount, or free within a quota?
9. **Retirement of an option used by a saved campaign.** Keep rendering old outputs (yes), but can a
   variation of an old production still use a retired option?
10. **Legacy registries.** Retire `characters` / `brand_characters` and the v1 `character_registry`
    routes, or keep them read-only?
11. **Adapter evaluation criteria.** What must the 750-step adapter pass to move EVALUATION →
    PRODUCTION, and does `REFERENCE_PLUS_ADAPTER` apply to all capabilities or only some (e.g. close-up
    portraits)?
12. **Nails.** The backend has a `NAILS` category; the Create flow doesn't list it. Drop, hide, or add
    to STYLE?
13. **Thumbnails.** Who produces option thumbnails, and must they be generated from EE-F-002 (so each
    is per character) or generic?

## 8. Implementation PR order

Each PR is small, additive, independently testable, and keeps the existing endpoints working.

*Status 2026-10-23:*
- 1 = #55 (merged)
- 2 = #57 (merged)
- 3 = #59 (in review)
- 4 = #60 (in review, stacked on #59)

From 5 on, the order is replaced by `APPEARANCE_STATUS.md` section 7 (AC-1 … AC-11):
- 5 and 6 become AC-1 to AC-5;
- 7 becomes AC-6 (`/appearance`);
- 11 is partly AC-7;
- 8–10 and 12–14 follow AC-11.

1. **Capability validation table + backfill** — `capability_validations` (add-if-missing
   migration), service, ORM rules; backfill a PROMOTED row for every option already in PRODUCTION.
   Tests: lifecycle, uniqueness, backfill idempotent, customer lists unchanged.
2. **Admin capability API** — register / validate / promote / retire / list (platform admin), audit
   log. Tests: role matrix, transitions, four-eyes (if decided), promote replaces previous version.
3. **Namespaced ids + option shape** — `customer_id`, `group`, `recommended` columns and backfill;
   the agreed option object on existing customer routes; old ids accepted as aliases on dispatch.
   Tests: ids unique per category, labels may repeat, no forbidden terms (shared assertion helper
   scanning every customer response).
4. **Reference sets** — `character_reference_sets` + items, immutability guards, admin API, EE-F-002
   V1 set. Tests: locked set can't change, hash verified at resolve.
5. **Strategy in the resolver** — `default_strategy` / `allowed_strategies`, adapter `EVALUATION`
   status, `REFERENCE_ONLY` plan with the reference set; adapters only for `REFERENCE_PLUS_ADAPTER`
   and PRODUCTION. Register the 750-step adapter at EVALUATION. Tests: EVALUATION/EXPERIMENTAL never
   in a plan; plan never in a customer response.
6. **Beauty directions** — table, admin API, customer `GET …/beauty-directions`, defaults/override
   validation in the resolver; seed the six as IN_DEVELOPMENT. Tests: defaults applied, overrides
   allowed/rejected, promotion requires promoted defaults.
7. **Style options endpoint** — `GET …/style-options` (hair, makeup, expression, jewelry), alias from
   `styling-options`. Tests: only promoted, per character.
8. **Poses by group + dress** — `group` on mappings, `dress` alias, new dress poses (Front, 3/4, Hand
   on Hip), label alignment, grouped response. Tests: every product type's catalogue, empty groups,
   unknown type 422.
9. **Camera options** — preset types + seeds, customer endpoint, framing rules per product type,
   resolver mapping. Tests: eyewear excludes full body, etc.
10. **Scene / lighting / campaign options** — namespaced, grouped customer endpoints on top of the
    presets registry. Tests: groups, promoted only.
11. **Generate v2** — `POST /api/v1/productions` with option ids only, `selection` stored, idempotency;
    `/productions/dispatch` kept and mapped. Tests: full request validation matrix, brand role,
    credits, 503 when unavailable, no forbidden terms.
12. **Progress stages** — `productions.stage`, worker updates, stage mapping in GET and websocket.
    Tests: stage order, FAILED refunds once.
13. **Outputs + review actions** — `production_outputs`, approve, variations (kept/changed),
    regenerate, download/export, save to campaign. Tests: approved outputs immutable, variation keeps
    unchanged elements, brand scoping on campaign, role matrix.
14. **Legacy cleanup** — freeze/retire v1 character registry and brand-character routes after the
    frontend moves (per open question 10).

## 9. Appearance / Styling Capabilities (Shahida, 2026-10-23)

Full detail is in `APPEARANCE_STATUS.md`. What changes in this document:

- **Three layers:** CHARACTER (locked) / APPEARANCE (styling) / PRODUCTION (photography). Appearance
  never creates a Character version and never changes EE-F-002 Core V1.0, the golden identity, the
  178 cm body profile or the reference set.
- **No duplicate registries.**
  - Appearance capabilities stay in `appearance_options` (definition, extended with runtime
    strategy, adapter strength, fallback strength, fallback capability, QA profile and thumbnail
    asset) plus `capability_validations` (per-character promotion, extended with `qa_notes` and the
    approved runtime snapshot).
  - Beauty directions stay `appearance_options` rows with a 1:1 `beauty_directions` extension for
    the recommended options. This replaces the global `beauty_directions` table in section 3.1.
  - QA profiles extend the existing `qa_profiles`.
  - New tables only where nothing fits: `runtime_profiles` and `capability_compatibility`.
- **Runtime profile.** A versioned `runtime_profiles` table, frozen once PRODUCTION, replaces the
  strategy columns planned on `character_runtime_v2` (section 3.2).
  - The legacy `character_runtime_profiles` / `character_runtime_v2`, with their 0.78
    `default_strength`, are not read by the resolver.
  - `REFERENCE_ONLY` is the default. `REFERENCE_PLUS_ADAPTER` uses `EE-F-002_CK0750` at 0.4, with
    0.6 as the stronger fallback; both values are data on the runtime profile or capability record,
    never code constants.
  - Customer productions only ever use a `PRODUCTION` adapter. `strategy_eligible` is dropped.
  - An automatic retry at 0.6 after an identity QA failure is **not decided**. It is a
    per-runtime-profile policy (`fallback_retry_enabled`), off by default, pending Shahida (cost
    and compute).
- **Lifecycle mapping.** Shahida's IN_DEVELOPMENT → VALIDATION → APPROVED → PRODUCTION → RETIRED
  is our REGISTERED → VALIDATING → VALIDATED → PROMOTED → RETIRED (definition statuses
  IN_DEVELOPMENT / VALIDATION / APPROVED / PRODUCTION / ARCHIVED). Promotion records `qa_notes` and
  the approved runtime profile.
- **Customer routes.** `GET /characters/{id}/appearance` (`hair_styles`, `makeup_styles`,
  `expressions`, `beauty_directions`) and `GET /characters/{id}/beauty-directions`, with
  `recommended_defaults: {hair_id, makeup_id, expression_id, grooming_id}`. These replace the
  planned `/style-options` (section 4.2); `/capabilities` and `/poses` stay.
- **Generation request.** It gains `character_version`, `product_id`,
  `appearance.{beauty_direction, hair_style, makeup_style, expression}` and
  `camera/scene/lighting_profile_id`. It refuses `lora_strength`, `checkpoint`, `workflow_node` and
  `reference_weight` with a 422.
- **Phases 8 and 9.** Phase 8 is the Admin Promotion Workflow, recording who validated and
  promoted, when, `qa_notes` and the approved `runtime_profile`. Phase 9 is the Frontend
  Integration Contract: appearance renders entirely from API results, with no frontend deploy when
  a style is promoted (`APPEARANCE_STATUS.md` 2.3).
- **Worker input.** `run_production` sends the AI worker no reference images, adapter or product
  image, so current generations are not identity-locked. The worker input contract is owned by
  Aryan.
- **Beauty direction list.** `CANONICAL_CONTROL`, `QUIET_LUXURY`, `LUXURY_WAVES`,
  `RUNWAY_EDITORIAL`, `CLASSIC_EVENING`, `MODERN_MINIMAL` (open question 1 resolved). The six in
  sections 4.3 and 6 are superseded.

## 10. Deviations of PRs #55–#60 from this design

| PR | Section | Design said | Built | Why |
|---|---|---|---|---|
| #55 capability validations | 3.1 | unique `customer_id` among non-retired rows | unique `customer_id` among **PROMOTED** rows, plus one PROMOTED version per capability (partial unique indexes) | a REGISTERED v2 shares the customer id of the PROMOTED v1 it will replace |
| #55 | 3.1 | lifecycle REGISTERED → VALIDATING → VALIDATED → PROMOTED → RETIRED (+ REJECTED) | plus REGISTERED → VALIDATED (record a validation without "start"), VALIDATED → VALIDATING, REJECTED → VALIDATING | rework without a new version |
| #55 | 3.1 | — | identity fields (character, version, type, key, capability version, customer id) are immutable; records are never deleted; bulk UPDATE/DELETE refused | same guard pattern as `character_registry_versions` |
| #55 | 3.1, Q12 | backfill everything in PRODUCTION | `NAILS` options are not backfilled (no capability type) | open question 12 |
| #55 | Q7 | four-eyes "if decided" | validator and promoter recorded separately, not enforced | open question 7 still open |
| #55 | 3.1 | backfill in a migration | `capability_validations_001` holds a frozen copy of the backfill rules; insert-only | migrations must not import app code |
| #56 Rosanne | 1.2 gap 12 | not in the PR order | strength / seed / workflow fields removed from `/api/v1/rosanne/*` responses | customer leakage |
| #57 admin API | 5 | register / validation / promote / retire / list | plus `POST …/validation/start`; `character_version` defaults to the current locked version; `is_default` / `recommended` set at promote | explicit VALIDATING step |
| #57 | 5 | promote "demotes" the previous version | the previous PROMOTED version is **RETIRED** (`replaced_version` in the response) | one PROMOTED version, no extra state |
| #57 | 5 | audit via `app/services/audit_service.py` | `app/services/audit.write_audit_log`, same transaction | `audit_service.log` doesn't work with the async session |
| #58 migrations on deploy | — | not in this design | the image runs `alembic upgrade head` before uvicorn (advisory lock); older migrations 36–42 guarded add-if-missing | production schema was behind the models |
| #59 option shape | 3.2, 8 (PR 3) | `customer_id` / `group` / `recommended` columns on `appearance_options`, `pose_definitions`, `presets`, with backfill | **no columns added**; these come from the PROMOTED `capability_validations` record; `capability_validations_002` re-runs the frozen backfill (insert-only) | one registry for per-character data; no definition-table migration |
| #59 | 4 | ids like `hair_canonical_straight`, `makeup_natural_minimal`, `scene_studio_white`, `campaign_ecommerce` | ids from existing keys: `hair_canonical`, `makeup_natural`, `expr_neutral_editorial`, `pose_walking`, `scene_env-stu-0001`, `lighting_<key>`, `campaign_ecommerce`; product types keep `garment`, `shoes`, `bags` … (no `dress` alias yet) | deterministic from existing data; renames are new capabilities |
| #59 | 4.2–4.6 | new `/style-options`, grouped `/poses`, `/scene-options`, `/campaign-options` | the existing routes (`/styling-options`, `/capabilities`, `/poses`, `/presets/*`) return the option shape; poses stay flat | smallest change; new routes come later (section 9) |
| #59 | 4 | `is_default` per character on the record | `is_default` from the definition tables (record value stored for later) | existing admin "set default" endpoints keep working |
| #59 | 2 | — | an option live in the definition table but not PROMOTED is **not offered** and dispatch refuses it (customer-safe 422); dispatch accepts the namespaced or the old id | fail closed |
| #60 reference sets | 6 | seed the set as PRODUCTION | the admin seed **locks** `EE-F-002_V1.0_REF_V1` and never promotes; promotion is a separate admin step; no migration writes it | Aryan/Shahida check the set first |
| #60 | 3.1 | `locked_*`, `content_hash` | plus `created_by`, `promoted_*`, `retired_*`, `retire_reason`; items carry `asset_id` and an FK to `canonical_assets` with `RESTRICT`; one item per asset per set | audit trail; no orphaned items |
| #60 | 1.2 gap 3 | canonical assets' role / QA / status mutable after lock | only the **file identity** (`asset_id`, `character_id`, `version`, `asset_role`, `storage_path`, `content_hash_sha256`) is frozen while the asset is in a non-DRAFT set; QA fields stay editable | QA can still be recorded |
| #60 | 5 | create / lock / promote | plus retire, `verify` (re-reads files from storage) and the seed endpoint; hashes re-checked on every resolve | tamper detection |
| #60 | 6 | roles face front, 3/4, profile, full body front, 3/4 | `face_front`, `face_34`, `profile`, `body_full`, `body_34`; `face_front` + `body_full` required to lock | **to be confirmed by Aryan/Shahida** |

