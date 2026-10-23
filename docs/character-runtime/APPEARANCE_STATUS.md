# Appearance / Styling Capabilities: design update and status

Status: report and design for review by Shahida, Indra and Aryan (2026-10-23). Docs only: no code,
migration or setting changes with this document. **No code starts until #58 → #59 → #60 are
merged** (in that order). This document translates Shahida's 10-phase Appearance / Styling
Capability direction to our stack (FastAPI, async SQLAlchemy, Alembic, Celery/Redis; Shahida's draft
used Prisma/NestJS/BullMQ) and says how it fits what PRs #55–#60 already built. `DESIGN.md` stays the
customer contract; where this document changes it, `DESIGN.md` section 9 points here.

File references are to `backend/`. "Today" means `main` plus the open PRs #58–#60.

## 0. Direction in one page

- **Three layers.**
  - **CHARACTER** (locked): EE-F-002 Eliska Novak Core V1.0, golden identity, the corrected 178 cm
    body profile, the immutable reference set.
  - **APPEARANCE** (styling): hair, makeup, expression, nails, jewelry, beauty direction.
  - **PRODUCTION** (photography): product, pose, camera, scene, lighting, campaign.
- **Appearance never touches the Character.** Choosing or promoting an appearance capability never
  creates a Character version, never edits `character_registry_versions` (LOCKED rows are already
  guarded), never edits the reference set (guarded by #60) and never edits the identity/body DNA.
- **Runtime.** `REFERENCE_ONLY` is the default. `REFERENCE_PLUS_ADAPTER` uses the EE-F-002 adapter
  `EE-F-002_CK0750` at strength **0.4**, with **0.6** as the stronger fallback. Both numbers live in
  data (the runtime profile and the capability record), never in a code constant. All of this is
  internal and never reaches a customer response. An automatic retry at the fallback strength is
  **not decided**: it is a per-runtime-profile policy, off by default (section 6, blocker 3).
- **Current generations are not identity-locked.** `run_production` sends the AI worker no reference
  images, no adapter and no product image (section 4.3). Fixing that needs the worker input contract
  from Aryan (section 6, blocker 1).
- **Lifecycle.** Shahida's `IN_DEVELOPMENT → VALIDATION → APPROVED → PRODUCTION → RETIRED` maps onto
  what we already have (section 1.2). Promotion also records `qa_notes` and the approved runtime
  profile.
- **Customers get promoted capabilities only** (APPROVED visibility is pending Shahida, section 6).
  Admins can list every status. Our namespaced ids and option shape stay.

## 1. Schema and model changes

### 1.1 Extend or add? (decision)

The direction lists five models. We already have tables for most of them. To avoid a second
registry, the rule is: **definitions stay in the definition tables, per-character validation and
promotion stay in `capability_validations`**, as built in #55/#59. New tables are added only where
nothing fits.

| Shahida's model | Our table | Decision | Why |
|---|---|---|---|
| `AppearanceCapability` | `appearance_options` (definition) + `capability_validations` (per-character status, promotion) | **Extend** `appearance_options` with the missing columns; extend `capability_validations` with the promotion record | `appearance_options` already has code, type, display name, version, status, character, character version, `adapter_id`, thumbnail, timestamps and the six types. A new `appearance_capabilities` table would duplicate it and the #59 customer routes that read it. |
| `BeautyDirection` | `appearance_options` rows with category `BEAUTY_DIRECTION` + **new** `beauty_directions` | **Add** a 1:1 extension table holding only the recommended defaults | Code, name, version, status and thumbnail already live on the `appearance_options` row, which also gives the lifecycle and the per-character promotion. The extension holds the typed foreign keys for the recommended hair/makeup/expression/grooming. This replaces the global `beauty_directions` table in `DESIGN.md` 3.1. |
| `CapabilityCompatibility` | none | **Add** `capability_compatibility` | Nothing records "X works / doesn't work with Y" today. It's per character version and generic over capability types, so it also covers poses and product types. |
| `CapabilityQAProfile` | `qa_profiles` (`app/models/db.py`, `QAProfile`; ids like `QA-PROFILE-CATALOG-001`) | **Extend** `qa_profiles` with two nullable columns | It already has a string id, weighted dimensions, hard gates and a pass threshold (`app/services/qa_service.py`). A second QA profile table would split the QA rules. |
| `CharacterRuntimeProfile` | `character_runtime_profiles` (v1 registry) and `character_runtime_v2`; neither is read by dispatch | **Add** `runtime_profiles` (class `RuntimeProfile`), versioned and frozen once in PRODUCTION | Both existing tables are mutable, unversioned and default `default_strength` to **0.78**, which is exactly the global strength the direction forbids. The name `character_runtime_profiles` is taken by the v1 table. The resolver will read only `runtime_profiles`; the two old tables are marked legacy and are never read for strategy or strength. |

Keys and versions: every Character Runtime table identifies the character version by the pair
`(character_id varchar(50), character_version varchar(10))`, for example `("EE-F-002", "1.0")`,
rather than a `character_version_id` foreign key. The new tables keep that pattern, which matches
`capability_validations`, `appearance_options` and `character_reference_sets`.

### 1.2 Lifecycle and type mapping

| Shahida | `appearance_options.status` (definition) | `capability_validations.status` (per character) | Customer sees it |
|---|---|---|---|
| IN_DEVELOPMENT | `IN_DEVELOPMENT` | `REGISTERED` | no |
| VALIDATION | `VALIDATION` | `VALIDATING` | no |
| APPROVED | `APPROVED` | `VALIDATED` | no (pending Shahida, section 6) |
| PRODUCTION | `PRODUCTION` | `PROMOTED` | **yes** |
| RETIRED | `ARCHIVED` | `RETIRED` | no |
| (check failed) | back to `IN_DEVELOPMENT` | `REJECTED` | no |

Today an admin drives two lifecycles: the definition status in `/admin/appearance/options` and the
capability record status in `/admin/characters/{id}/capabilities`. The customer routes (#59) need both
(`PRODUCTION` **and** `PROMOTED`). **Proposal (PR AC-8):** promoting a capability record moves its
appearance definition to `PRODUCTION` in the same transaction, and retiring it moves the definition to
`ARCHIVED`, so in practice there is one lifecycle to drive. The definition endpoints stay for editing
labels, thumbnails and runtime fields while the option isn't live.

| Shahida's type | `appearance_options.category` | `capability_validations.capability_type` | customer id prefix |
|---|---|---|---|
| HAIR_STYLE | `HAIR_STYLE` | `HAIR` | `hair_` |
| MAKEUP_STYLE | `MAKEUP_STYLE` | `MAKEUP` | `makeup_` |
| EXPRESSION | `EXPRESSION` | `EXPRESSION` | `expr_` |
| BEAUTY_DIRECTION | `BEAUTY_DIRECTION` | `BEAUTY_DIRECTION` | `beauty_` |
| NAILS | `NAILS` | **new** `NAILS` (code-only list change) | `nails_` |
| JEWELRY | `JEWELRY` | `JEWELRY` | `jewelry_` |

Capability types are a code list (`app/services/capability_validations.py` `CAPABILITY_TYPES`), not a
database enum, so adding `NAILS` needs no migration. "Grooming" has no type yet (section 6).

### 1.3 Table by table

All migrations are additive: new tables use `create_table_if_absent`, new columns and indexes are
added only if missing (the #58 helpers `add_column_if_absent` / `create_index_if_absent`), every new
column is nullable or has a default, and nothing is dropped or rewritten. **No migration writes seed
data**: like the #60 reference set, the Phase 3 seed is an admin action. They chain after
`reference_sets_001` (#60), so there's always one alembic head.

**Migration `runtime_profiles_001` (PR AC-1)**

New table `runtime_profiles`: the approved way to run one character version.

| column | type | notes |
|---|---|---|
| id | int PK | |
| runtime_profile_id | varchar(60) unique | `EE-F-002_V1.0_RT_V1` |
| character_id, character_version | varchar(50), varchar(10) | index |
| version | int | per character version |
| status | varchar(20) | `DRAFT → PRODUCTION → RETIRED`; one `PRODUCTION` per character version (partial unique index) |
| default_strategy | varchar(30) | `REFERENCE_ONLY` (default) |
| allowed_strategies | jsonb | `["REFERENCE_ONLY"]` or `["REFERENCE_ONLY", "REFERENCE_PLUS_ADAPTER"]` |
| reference_set_id | int FK `character_reference_sets.id` null, `RESTRICT` | pins the set; must be LOCKED or PRODUCTION |
| adapter_id | varchar(50) null | `model_artifacts.model_id`, e.g. `EE-F-002_CK0750` |
| adapter_strength | float null | `0.4`; CHECK `0 < x <= 1` |
| fallback_adapter_strength | float null | `0.6`; CHECK `adapter_strength < x <= 1` |
| qa_profile_id | varchar(100) null | `qa_profiles.qa_profile_id`, the character's default QA profile |
| fallback_retry_enabled | bool, default **false** | the automatic-retry policy: when true, an output that fails the identity gate under `REFERENCE_PLUS_ADAPTER` is regenerated once at `fallback_adapter_strength`. Off until Shahida decides (blocker 3) |
| notes | text null | |
| created_by, created_at | | |
| promoted_by, promoted_at, retired_by, retired_at, retire_reason | | |

Unique `(character_id, character_version, version)`. ORM guards in the style of #55/#60: a
`PRODUCTION` or `RETIRED` row changes only its status (forward) and the promote/retire fields; no
delete; no bulk UPDATE/DELETE. Every write is audit-logged (`app/services/audit.write_audit_log`).

`model_artifacts` gains no columns. `EVALUATION` joins the status vocabulary in code
(`EXPERIMENTAL → EVALUATION → PRODUCTION → ARCHIVED`). `EE-F-002_CK0750` is registered by an admin
action at `EVALUATION`, with its real `storage_path` and `checksum_sha256`. The `strategy_eligible`
column from `DESIGN.md` 3.2 is dropped: an adapter may be used only when it is `PRODUCTION` **and**
named by a PRODUCTION runtime profile (or a promoted capability's runtime snapshot).

**Migration `appearance_capabilities_001` (PR AC-2)**

1. `appearance_options`, new columns (the missing `AppearanceCapability` fields):

   | column | type | notes |
   |---|---|---|
   | runtime_strategy | varchar(30) null | `REFERENCE_ONLY` / `REFERENCE_PLUS_ADAPTER`; null = the runtime profile's default |
   | adapter_strength | float null | overrides the runtime profile's strength for this capability (e.g. `0.4`) |
   | fallback_adapter_strength | float null | overrides the stronger fallback (e.g. `0.6`) |
   | fallback_capability_id | int FK `appearance_options.id` null, `RESTRICT` | same character version and category (service rule), e.g. `LOW_CHIGNON → CANONICAL` |
   | qa_profile_id | varchar(100) null | `qa_profiles.qa_profile_id` |
   | thumbnail_asset_id | int FK `assets.id` null, `SET NULL` | `thumbnail_url` stays and is used when this is null |

   The existing `adapter_id` is Shahida's `adapter_id`. Today it must be an `APPEARANCE`-layer
   adapter (`appearance_options._check_adapter`). This is widened to also accept the character
   version's `IDENTITY` adapter, and when it is null the runtime profile's adapter is used.
   `promoted_at` is not duplicated here; it is the capability record's `promoted_at`. These columns
   are editable only while the option isn't live (the existing edit rule).

2. New table `beauty_directions` (1:1 with an `appearance_options` row of category `BEAUTY_DIRECTION`):

   | column | type | notes |
   |---|---|---|
   | id | int PK | |
   | appearance_option_id | int FK `appearance_options.id` unique, `RESTRICT` | code, display name, version, status, thumbnail come from this row |
   | recommended_hair_option_id | int FK `appearance_options.id` null | category `HAIR_STYLE` |
   | recommended_makeup_option_id | int FK `appearance_options.id` null | category `MAKEUP_STYLE` |
   | recommended_expression_option_id | int FK `appearance_options.id` null | category `EXPRESSION` |
   | recommended_grooming_option_id | int FK `appearance_options.id` null | category to be decided (section 6) |
   | overridable | jsonb | default `["hair", "makeup", "expression", "grooming"]` |
   | created_at, updated_at | | |

   Service rules: every recommended option must belong to the same character version and the right
   category. A direction can be promoted only when every recommended option is promoted. An option
   recommended by a promoted direction can't be retired until that direction is retired or replaced
   by a new version. The row is frozen while its direction is live.

3. New table `capability_compatibility`:

   | column | type | notes |
   |---|---|---|
   | id | int PK | |
   | character_id, character_version | varchar | index |
   | subject_type, subject_key | varchar(30), varchar(80) | e.g. `HAIR`, `SLICK_BACK` |
   | object_type, object_key | varchar(30), varchar(80) | e.g. `PRODUCT_TYPE`, `headwear`; `MAKEUP`, `EDITORIAL`; `POSE`, `hand_on_hip` |
   | rule | varchar(20) | `BLOCKED` or `DISCOURAGED`; no row = compatible |
   | reason | text | admin-only |
   | created_by, created_at, retired_by, retired_at | | |

   Unique `(character_id, character_version, subject_type, subject_key, object_type, object_key)`
   among non-retired rows (partial index). Lookups check both directions. The table and model land in
   AC-2 (P0 schema); the rules are used from AC-11 (P2).

4. `qa_profiles`, new columns: `capability_type varchar(30) null` and `character_id varchar(50)
   null`. That turns a QA profile into a `CapabilityQAProfile` (for example
   `QA-PROFILE-APPEARANCE-HAIR-001` with hard gates on identity and face) without a new table.

5. `capability_validations`, new columns (the promotion record):
   - `qa_notes text null`;
   - `runtime_profile jsonb null`: the approved runtime snapshot, written at promotion:
     `{runtime_profile_id, runtime_profile_version, strategy, adapter_id, adapter_strength,
     fallback_adapter_strength, fallback_customer_id, qa_profile_id}`.

   Both are written once, by the promote action, and then frozen (added to the before-update
   guard). Both are admin-only.

**Migration `production_selection_001` (PR AC-7)**

`productions.selection jsonb null`: the customer-safe resolved selection (namespaced ids after
beauty-direction defaults), returned on the generation response and kept for variations. The
internal plan stays in the admin-only `productions.runtime_profile`.

**No migration:** the CapabilityResolver (AC-4), the strategy in the resolver (AC-5), the read APIs
(AC-6), promotion (AC-8), the frontend contract (AC-9), the E2E run (AC-10) and recommendation/fallback/QA logic (AC-11).

### 1.4 What is never written by appearance

`character_registry_versions`, `characters_v2`, `character_identity_dna`, `character_body_dna`,
`canonical_assets` file fields, `character_reference_sets` / items. The EE-F-002 Core V1.0 row stays
LOCKED at 178 cm, `TALL`, `HIGH_FASHION_RUNWAY_SLIM`. Each of the new PRs keeps a test that runs its
writes and asserts those rows are byte-identical before and after.

## 2. API routes

All routes are under `/api/v1`. Customer routes need a logged-in user, return PROMOTED capabilities
only, use the namespaced ids and the option object (`id, label, thumbnail_url, group, is_default,
recommended`, plus `description`), and never contain the forbidden terms (`DESIGN.md` section 0;
the shared `tests/customer_safety.py` check from #59 is applied to every new route). Admin routes
need `require_platform_admin` and return internal fields.

### 2.1 Customer

| Route | State | Notes |
|---|---|---|
| `GET /characters/{id}/capabilities` | exists (#59 in review: promoted only, option shape) | product types; AC-6 adds `appearance_types` additively (which appearance types have at least one promoted option). `product_types` is unchanged because the frontend already reads it. |
| `GET /characters/{id}/appearance` | **new (AC-6)** | `{hair_styles, makeup_styles, expressions, beauty_directions}`, plus `nails` and `jewelry` once they have promoted options. The frontend already calls it (`lib/characterRegistryApi.js` `getAppearance`, commit 2235f5e) and gets 404 today. |
| `GET /characters/{id}/beauty-directions` | **new (AC-6)** | each direction with `recommended_defaults: {hair_id, makeup_id, expression_id, grooming_id}`. The frontend already calls it (`getBeautyDirections`) and reads `recommended_defaults` (falling back to `defaults`). |
| `GET /characters/{id}/poses?product_type=` | exists (#59 in review) | unchanged; groups come later (`DESIGN.md` PR 8) |
| `GET /characters/{id}/styling-options` | exists (#59 in review) | kept as an alias of `/appearance` in the old shape until the frontend moves; then frozen |
| `POST /productions/dispatch` | exists | AC-7 adds the Phase 7 fields and rejects technical fields (section 4.1). The proposed `POST /productions` (`DESIGN.md` 4.7) becomes the same handler. |
| `GET /productions/{id}` | exists | AC-7 adds `selection` |

Unknown character: 404 (same message as today). A character with no promoted appearance yet: 200
with empty lists.

> **The frontend already calls `/appearance` and `/beauty-directions`, and both 404 until AC-6.**
> They're called in `lib/characterRegistryApi.js` (`getAppearance`, `getBeautyDirections`, main
> commit 2235f5e). Until AC-6 is deployed, and on any 404 from them later, the frontend must fall
> back gracefully:
> - **Appearance:** use `GET /characters/{id}/styling-options`, which exists and returns the same
>   option objects under `hair`, `makeup`, `expression` and `beauty_direction`.
> - **Beauty directions:** if they aren't available, hide the section.
> - **No error state:** don't show an error banner and don't block the page.
>
> A 404 for an unknown *character* has the same status code. The frontend tells the two apart by
> whether `/styling-options` for that character also returns 404.

### 2.2 Admin (platform admin)

| Route | State | Notes |
|---|---|---|
| `POST/GET /admin/appearance/options`, `PATCH /admin/appearance/options/{internal_key}`, `POST …/status`, `POST …/default` | exist | AC-2 adds the new runtime fields to the create/patch bodies |
| `POST /admin/appearance/beauty-directions/{internal_key}/defaults` | **new (AC-2)** | set the recommended options of a direction while it isn't live |
| `GET /admin/characters/{id}/appearance?status=&character_version=` | **new (AC-6)** | same shape as the customer route plus `status`, `internal_key`, versions and runtime fields, for **every** status. This is how admins "request all statuses". The customer route never changes shape by role. |
| `GET /admin/characters/{id}/capabilities?type=&status=` | exists (#57) | capability records, every status |
| `POST /admin/characters/{id}/capabilities` (register), `…/validation/start`, `…/validation`, `…/retire` | exist (#57) | unchanged |
| `POST /admin/characters/{id}/capabilities/{type}/{key}/promote` | exists (#57) | AC-8: body gains required `qa_notes`; the response returns the promotion record with the approved `runtime_profile` |
| `POST /admin/characters/{id}/capabilities/{type}/{key}/resolve` | **new (AC-4)** | dry run of the CapabilityResolver for one capability (section 4.2); writes nothing |
| `POST /admin/characters/{id}/compatibility`, `GET …/compatibility`, `POST …/compatibility/{rule_id}/retire` | **new (AC-11)** | compatibility rules |
| `POST /admin/characters/{id}/runtime-profiles`, `GET …`, `POST …/{runtime_profile_id}/promote`, `POST …/retire` | **new (AC-1)** | runtime profiles; promote refuses `REFERENCE_PLUS_ADAPTER` in `allowed_strategies` unless the adapter is `PRODUCTION` |
| `POST /admin/training/adapters/{adapter_id}/status` | **new (AC-1)** | `EXPERIMENTAL → EVALUATION → PRODUCTION / ARCHIVED`; registers `EE-F-002_CK0750` at `EVALUATION` |
| `POST /admin/characters/EE-F-002/appearance/seed` | **new (AC-3)** | Phase 3 seed; idempotent; never promotes |
| `POST /admin/productions/plan` | **new (AC-5)** | dry-run the runtime resolver for a generation request and return the internal plan; nothing charged or queued |
| `/admin/characters/{id}/reference-sets/*` | #60 in review | unchanged |

### 2.3 Frontend integration contract (Phase 9)

Goal: Hair, Makeup, Expression and Beauty Direction render **entirely from API results**. Promoting a
new style (register → validate → promote, all admin API) makes it appear for customers with **no
frontend deploy and no backend deploy**.

**Backend promises** (enforced by tests in AC-9):
- **Fixed keys.** The list keys are fixed: `hair_styles`, `makeup_styles`, `expressions`,
  `beauty_directions`; later `nails` and `jewelry`, added only additively.
- **Every option carries what the UI needs.** That's `id`, `label`, `thumbnail_url`, `group`,
  `is_default`, `recommended` and `description`. Array order is the display order (`sort_order`).
  Exactly one `is_default: true` per list when the list isn't empty.
- **Beauty directions carry their defaults.** `recommended_defaults` holds `hair_id`, `makeup_id`,
  `expression_id` and `grooming_id` (each a promoted id from the same response, or null) and
  `overridable`.
- **Only additive changes.** New fields may appear; existing fields never change meaning or type.
  A retired option simply stops being listed. An empty list means "nothing to offer".
- **Ids are opaque and stable.** The id a customer saw is accepted by dispatch unchanged. Old ids
  stay accepted as aliases.

**Frontend rules** (Indra):
- **No hard-coded styles.** No style ids, labels, thumbnails or per-style code. The only names the
  frontend knows are the list keys and option fields above.
- **Render from the response.** Groups come from `group`, preselection from `is_default`, badges
  from `recommended`. Choosing a beauty direction preselects its `recommended_defaults` and allows
  changing only the `overridable` pieces.
- **Send ids back exactly as received.** Today `characterRegistryApi.dispatchProduction` strips the
  `hair_` / `makeup_` / `expr_` / `pose_` / `scene_` / `lighting_` / `campaign_` prefixes and
  upper-cases scene and lighting ids (main commit 8988554). Dispatch accepts that for now, but the
  contract is to send the namespaced id unchanged.
- **Ignore what you don't know.** Ignore unknown fields. Hide a section whose list is empty or
  whose route 404s (section 2.1).

## 3. Example payloads

The ids below are what the existing backfill rule produces (`hair_` + lower(option_id) and so on;
#55/#59). `hair_canonical`, `makeup_natural` and `expr_neutral_editorial` are already PROMOTED for
EE-F-002 V1.0. The others appear only after they are validated and promoted.

### 3.1 `GET /api/v1/characters/EE-F-002/appearance`

After `LOW_CHIGNON`, `POLISHED_NUDE`, `SOFT_CONFIDENCE` and `QUIET_LUXURY` are promoted:

```json
{
  "character_id": "EE-F-002",
  "character_version": "1.0",
  "hair_styles": [
    { "id": "hair_canonical", "label": "Canonical Straight", "thumbnail_url": "https://cdn.modelens.ai/appearance/ee-f-002/hair-canonical.jpg",
      "group": null, "is_default": true, "recommended": true,
      "description": "Sleek natural center-part editorial straight." },
    { "id": "hair_low_chignon", "label": "Low Chignon", "thumbnail_url": "https://cdn.modelens.ai/appearance/ee-f-002/hair-low-chignon.jpg",
      "group": "Polished", "is_default": false, "recommended": true,
      "description": "Low, smooth chignon at the nape." }
  ],
  "makeup_styles": [
    { "id": "makeup_natural", "label": "Natural Minimal", "thumbnail_url": "https://cdn.modelens.ai/appearance/ee-f-002/makeup-natural.jpg",
      "group": null, "is_default": true, "recommended": true,
      "description": "Clean bare-skin finish with subtle hydration." },
    { "id": "makeup_polished_nude", "label": "Polished Nude", "thumbnail_url": "https://cdn.modelens.ai/appearance/ee-f-002/makeup-polished-nude.jpg",
      "group": "Soft", "is_default": false, "recommended": true,
      "description": "Refined nude tones, satin skin." }
  ],
  "expressions": [
    { "id": "expr_neutral_editorial", "label": "Neutral Editorial", "thumbnail_url": "https://cdn.modelens.ai/appearance/ee-f-002/expr-neutral-editorial.jpg",
      "group": null, "is_default": true, "recommended": true,
      "description": "High-fashion, poised and confident." },
    { "id": "expr_soft_confidence", "label": "Soft Confidence", "thumbnail_url": "https://cdn.modelens.ai/appearance/ee-f-002/expr-soft-confidence.jpg",
      "group": "Warm", "is_default": false, "recommended": false,
      "description": "Relaxed, assured, a hint of warmth." }
  ],
  "beauty_directions": [
    { "id": "beauty_quiet_luxury", "label": "Quiet Luxury", "thumbnail_url": "https://cdn.modelens.ai/appearance/ee-f-002/beauty-quiet-luxury.jpg",
      "group": "Luxury", "is_default": false, "recommended": true,
      "description": "Understated polish: low chignon, polished nude, soft confidence." }
  ]
}
```

Keys are snake_case like every other route (`hair_styles`, not `hairStyles`; section 6).

### 3.2 `GET /api/v1/characters/EE-F-002/beauty-directions`

```json
{
  "character_id": "EE-F-002",
  "character_version": "1.0",
  "beauty_directions": [
    {
      "id": "beauty_quiet_luxury",
      "label": "Quiet Luxury",
      "thumbnail_url": "https://cdn.modelens.ai/appearance/ee-f-002/beauty-quiet-luxury.jpg",
      "group": "Luxury",
      "is_default": false,
      "recommended": true,
      "description": "Understated polish: low chignon, polished nude, soft confidence.",
      "recommended_defaults": {
        "hair_id": "hair_low_chignon",
        "makeup_id": "makeup_polished_nude",
        "expression_id": "expr_soft_confidence",
        "grooming_id": null
      },
      "overridable": ["hair_id", "makeup_id", "expression_id", "grooming_id"]
    },
    {
      "id": "beauty_canonical_control",
      "label": "Canonical Control",
      "thumbnail_url": "https://cdn.modelens.ai/appearance/ee-f-002/beauty-canonical-control.jpg",
      "group": "Signature",
      "is_default": true,
      "recommended": false,
      "description": "Eliska's canonical look.",
      "recommended_defaults": {
        "hair_id": "hair_canonical",
        "makeup_id": "makeup_natural",
        "expression_id": "expr_neutral_editorial",
        "grooming_id": null
      },
      "overridable": ["hair_id", "makeup_id", "expression_id", "grooming_id"]
    }
  ]
}
```

`grooming_id` is always present and `null` until grooming is defined (section 6). Every non-null id
in `recommended_defaults` is a promoted option of this character version (enforced at promotion), so
the frontend can preselect it without another check. `CANONICAL_CONTROL`'s defaults are my reading of
"canonical"; only `QUIET_LUXURY`'s are given in the direction.

### 3.3 `GET /api/v1/characters/EE-F-002/capabilities`

```json
{
  "character_id": "EE-F-002",
  "product_types": [
    { "id": "garment", "label": "Garment", "description": "Validated apparel capability for EE-F-002.",
      "thumbnail_url": "https://cdn.modelens.ai/capabilities/ee-f-002/garment.jpg",
      "group": null, "is_default": true, "recommended": false }
  ],
  "appearance_types": ["hair_styles", "makeup_styles", "expressions", "beauty_directions"]
}
```

`product_types` is exactly the #59 shape. `appearance_types` is the only addition.

### 3.4 Admin promotion record

```json
POST /api/v1/admin/characters/EE-F-002/capabilities/HAIR/LOW_CHIGNON/promote
{ "capability_version": 1, "is_default": false, "recommended": true,
  "qa_notes": "Identity 96.1 / face 95.4 across 24 samples at 0.4; no drift at 3/4. Two hairline artefacts at 4K; re-run at 0.6 by hand, both clean." }

200
{
  "character_id": "EE-F-002",
  "character_version": "1.0",
  "capability_type": "HAIR",
  "capability_key": "LOW_CHIGNON",
  "capability_version": 1,
  "customer_id": "hair_low_chignon",
  "status": "PROMOTED",
  "validated_by": "aryan@modelens.ai",
  "validated_at": "2026-11-03T09:00:00Z",
  "promoted_by": "anshu@modelens.ai",
  "promoted_at": "2026-11-03T10:00:00Z",
  "replaced_version": null,
  "qa_notes": "Identity 96.1 / face 95.4 across 24 samples at 0.4; no drift at 3/4. Two hairline artefacts at 4K; re-run at 0.6 by hand, both clean.",
  "runtime_profile": {
    "runtime_profile_id": "EE-F-002_V1.0_RT_V1",
    "runtime_profile_version": 1,
    "strategy": "REFERENCE_PLUS_ADAPTER",
    "adapter_id": "EE-F-002_CK0750",
    "adapter_strength": 0.4,
    "fallback_adapter_strength": 0.6,
    "fallback_customer_id": "hair_canonical",
    "qa_profile_id": "QA-PROFILE-APPEARANCE-HAIR-001"
  },
  "validation": {
    "checks": { "identity": "PASS", "face": "PASS", "body": "PASS", "product": "PASS" },
    "evidence": { "sample_production_ids": ["prd_val_101", "prd_val_102"], "notes": "24 samples." }
  }
}
```

The server builds `runtime_profile` from the capability's definition and the character's PRODUCTION
runtime profile at the moment of promotion. The caller can't send it. Promotion is refused (409) when:
- the record isn't `VALIDATED`;
- the strategy is `REFERENCE_PLUS_ADAPTER` and the adapter isn't `PRODUCTION`, or the runtime
  profile doesn't allow that strategy;
- it's a beauty direction and one of its recommended options isn't promoted.

The snapshot never changes after promotion. A new runtime needs a new capability version.

## 4. Runtime resolver flow

Two services, both extending what exists:

- **CapabilityResolver** (new `app/services/capability_resolver.py`, AC-4) answers questions about
  one capability.
- **Runtime resolver** (`app/services/production_dispatch.resolve_runtime_profile`, AC-5) builds the
  whole plan. It writes nothing until dispatch reserves credits.

### 4.1 Request (Phase 7)

```json
POST /api/v1/productions/dispatch          (Idempotency-Key supported)
{
  "brand_id": 12,
  "character_id": "EE-F-002",
  "character_version": "1.0",
  "product_id": 1042,
  "appearance": {
    "beauty_direction": "beauty_quiet_luxury",
    "hair_style": null,
    "makeup_style": null,
    "expression": null
  },
  "pose_id": "pose_standing",
  "camera_profile_id": "camera_full_body",
  "scene_profile_id": "scene_env-stu-0001",
  "lighting_profile_id": "lighting_studio_soft_diffuse",
  "campaign_preset_id": "campaign_ecommerce",
  "aspect_ratio": "4:5",
  "count": 4
}
```

- **Ids only.** A `null` piece is filled from the beauty direction, then from the character default.
- **Old field names still work.** `product_asset_url`, `appearance.hair` / `makeup` / `expression`,
  `location_id`, `lighting_id` and `campaign_preset` stay as aliases until the frontend moves.
- **Technical fields are refused.** `lora_strength`, `checkpoint`, `workflow_node` and
  `reference_weight` (and their camelCase forms `loraStrength`, `workflowNode`, `referenceWeight`),
  plus any other unknown field, get a **422** with a customer-safe message. That message names the
  field, never a value: "`lora_strength` can't be set on a production request."
- **`camera_profile_id` is optional** until camera options exist (`DESIGN.md` PR 9). Until then the
  campaign's camera is used and any value other than null gets a 422.

### 4.2 CapabilityResolver (Phase 5)

For `(character, version, capability_type, id)`, with `id` being the namespaced or old id:

| Question | Answer from |
|---|---|
| Is it valid for this character? | a `capability_validations` record for this character version, any status, with a definition row of the same character version |
| Is it production-ready? | record `PROMOTED` **and** definition live (`PRODUCTION` / `ACTIVE`) **and** its approved `runtime_profile` is still satisfiable (adapter still `PRODUCTION`, runtime profile still `PRODUCTION`) |
| Does it need an adapter? | the promoted snapshot's `strategy == REFERENCE_PLUS_ADAPTER` |
| Preferred strategy | the snapshot's `strategy`; for a not-yet-promoted record (admin dry run), the definition's `runtime_strategy`, otherwise the runtime profile's `default_strategy` |
| Fallback | strength: snapshot `fallback_adapter_strength`; capability: snapshot `fallback_customer_id` (must itself be production-ready, checked here) |
| Compatible with the rest of the selection? | `capability_compatibility` (AC-11): `BLOCKED` → not allowed; `DISCOURAGED` → allowed, flagged on the plan |

Customer callers only ever get yes/no as "available / not available". Admin callers (the `/resolve`
dry run) get the full answer.

### 4.3 Runtime resolver, step by step (Phase 6)

1. **Refuse technical fields** (section 4.1). 422.
2. **Character version.** The current LOCKED version (`character_versions.get_current_locked_version`).
   Unknown character: 404. A `character_version` that isn't the current locked one: 422.
3. **Runtime profile.** The `PRODUCTION` `runtime_profiles` row for the version. None: **503** "not
   available yet, nothing charged".
4. **Reference assets.** `reference_sets.production_set` (#60). The hashes are re-checked on every
   resolve. No PRODUCTION set or an integrity error: **503**, nothing charged, plus an admin
   audit/alert entry. If the runtime profile pins a set, it must be that set.
5. **Product workflow.** The product type must be promoted and its pack `PRODUCTION`; the pack gives
   the workflow route and the product QA rules (existing). Not available: 503 as today.
6. **Appearance selection.**
   1. If `beauty_direction` is set, it must be production-ready (otherwise 422 on
      `appearance.beauty_direction`). Its recommended options fill every null piece.
   2. A piece set explicitly must be production-ready. If a direction is set, the piece must also be
      `overridable`, or equal to the direction's default; otherwise 422 naming the field.
   3. A piece still empty gets the character default (`is_default`, today `CANONICAL` / `NATURAL` /
      `NEUTRAL_EDITORIAL`).
7. **Compatibility.** Check every selected pair (appearance × appearance, appearance × product type,
   appearance × pose). `BLOCKED` gives a 422 naming both fields ("Slick Back isn't available with
   Headwear"); `DISCOURAGED` is recorded on the plan for QA.
8. **Strategy.**
   - If any selected capability's snapshot says `REFERENCE_PLUS_ADAPTER`, the strategy is
     `REFERENCE_PLUS_ADAPTER`; otherwise it's the runtime profile's `default_strategy`
     (`REFERENCE_ONLY`).
   - The chosen strategy must be in the runtime profile's `allowed_strategies`. Otherwise the
     capability is not production-ready: 503 "temporarily unavailable", nothing charged. This can't
     normally happen, because promotion checks it.
9. **Adapter** (only for `REFERENCE_PLUS_ADAPTER`; with `REFERENCE_ONLY` the plan has
   `"adapter": null`).
   - **Which adapter:** the snapshot `adapter_id`, else the runtime profile's `adapter_id`. It must
     be a `model_artifacts` row of this character version with status **`PRODUCTION`** and a checksum.
     `EVALUATION` / `EXPERIMENTAL` / `ARCHIVED` are never used for a customer production. Not usable:
     503, nothing charged, admin alert. **There is no silent fallback to `REFERENCE_ONLY` and no
     silent swap to `fallback_customer_id`**: the customer chose that look (decision in section 6).
   - **`strength`:** the highest `adapter_strength` among the selected capabilities' snapshots, else
     the runtime profile's (`0.4`).
   - **`fallback_strength`:** likewise from `fallback_adapter_strength` (`0.6`). It is recorded on the
     plan but used automatically only when the runtime profile's `fallback_retry_enabled` is true
     (default false). Otherwise it's there for an admin re-run.
   - Both values are always taken from those records. There is no constant in code; a missing value
     with `REFERENCE_PLUS_ADAPTER` is a 503 and an admin alert.
10. **Pose, camera, scene, lighting, campaign.** Resolved through `customer_options` as #59 does today
    (namespaced or old ids, customer-safe 422). Camera comes from `camera_profile_id` once camera
    options exist, otherwise from the campaign.
11. **QA profiles.**
    - The product pack's QA rules, the runtime profile's `qa_profile_id`, and every selected
      capability's `qa_profile_id`.
    - The identity hard gate is the strictest of them.
12. **Plan** (`profile_version` 2, admin-only on `productions.runtime_profile`):

    ```json
    { "profile_version": 2,
      "character": { "character_id": "EE-F-002", "version": "1.0", "locked": true },
      "runtime_profile": { "runtime_profile_id": "EE-F-002_V1.0_RT_V1", "version": 1 },
      "strategy": "REFERENCE_PLUS_ADAPTER",
      "reference_set": { "reference_set_id": "EE-F-002_V1.0_REF_V1", "content_hash": "…",
                         "items": [ { "role": "face_front", "asset_id": "…", "sha256": "…" } ] },
      "adapter": { "adapter_id": "EE-F-002_CK0750", "strength": 0.4, "fallback_strength": 0.6 },
      "appearance": [ { "type": "HAIR", "key": "LOW_CHIGNON", "version": 1, "customer_id": "hair_low_chignon",
                        "source": "beauty_direction" } ],
      "workflow": { "route": "…", "provider_route": { "…": "…" }, "fallback_route": { "…": "…" } },
      "layers": { "product": { "…": "…" }, "pose": { "…": "…" }, "camera": { "…": "…" },
                  "scene": { "…": "…" }, "lighting": { "…": "…" } },
      "qa_profiles": ["QA-PROFILE-CATALOG-001", "QA-PROFILE-APPEARANCE-HAIR-001"],
      "flags": [],
      "params": { "count": 4, "aspect_ratio": "4:5", "quality": "…", "resolution": "2K", "seed": 123 } }
    ```

    `productions.selection` gets the customer-safe resolved ids only.
13. **Dispatch.**
    1. Credits are reserved once (existing ledger) and `process_production_job` is enqueued on Celery
       (Redis broker).
    2. `run_production` sends the plan to the AI worker.
    3. Outputs are registered as brand assets and QA is scored with the plan's profiles.
    4. If the identity gate fails, the output is marked for review and not delivered.
    5. **Automatic retry, only if enabled.** If the runtime profile's `fallback_retry_enabled` is true
       (default **false**) and the strategy is `REFERENCE_PLUS_ADAPTER`, the worker first regenerates
       that output once at `fallback_strength`, and only then marks it for review if it still fails.
       Whether to enable this is blocker 3: each retry is a full extra generation (compute cost),
       and who pays for it is open.
    6. A failed production refunds once (existing helper).
    7. Then comes review.

**Current generations are not identity-locked (blocker 1).** `run_production` today sends ComfyUI
only `scene_description`, `pose_filename`, `aspect_ratio` and `resolution` (`production_dispatch.py`
`_comfyui` → `generation_pipeline.run_with_timeout`).
- **Nothing that carries identity reaches the worker:** no reference images, no adapter and no
  product image. Appearance and strength don't either.
- **The plan is ignored.** Whatever the resolver puts in the plan, the image comes from the base
  workflow plus a scene text.

AC-5 adds them to the worker input, but needs the AI worker's input contract from **Aryan**.

## 5. Status of the 10 phases

PR states: #55, #56 and #57 are merged; #58, #59 and #60 are open (in review).

| Phase | What | Status | PRs |
|---|---|---|---|
| 1 | Schema | **Partly done.** Done or in review: per-character capability records (`capability_validations`, #55 merged) with re-backfill (`capability_validations_002`, #59 in review); immutable reference sets (#60 in review); migrations on deploy plus guards on the older migrations (#58 in review). `appearance_options` predates #55. Planned: `runtime_profiles`, appearance runtime columns, `beauty_directions`, `capability_compatibility`, `qa_profiles` columns, promotion columns. | #55, #58, #59, #60; planned AC-1, AC-2 |
| 2 | Models kept separate from Character | **Partly done.** Appearance and capability records never write to the Character (guards and tests in #55, #57, #60). The five new models are planned. | #55, #57, #60; planned AC-1, AC-2 |
| 3 | Seed (validation stage, not promoted) | **Planned.** Only the V1.0 canonical defaults exist (`CANONICAL`, `NATURAL`, `NEUTRAL_EDITORIAL`, PROMOTED by the #55 backfill). | planned AC-3 |
| 4 | Read APIs | **Partly in review.** `/capabilities`, `/styling-options` and `/poses` return PROMOTED only with namespaced ids and the option shape (#59). The admin list of every status exists for capability records (#57). Planned: `/appearance`, `/beauty-directions`, admin `/appearance?status=`. | #57, #59; planned AC-6 |
| 5 | CapabilityResolver | **Partly in review.** "Valid and promoted for the character" plus old/new id matching is `customer_options` (#59). Planned: production-ready via runtime snapshot, adapter need, strategy, fallback, compatibility. | #59; planned AC-4 |
| 6 | Runtime resolver | **Partly.** `resolve_runtime_profile` builds an admin-only plan today (pre-runtime code). The PRODUCTION reference set read with hash re-check is ready (#60) but not wired in. Planned: runtime profile, strategy, adapter gate, QA profiles, worker input. | #60; planned AC-5 |
| 7 | Generation request | **Partly in review.** Dispatch takes option ids and accepts namespaced or old ids with a customer-safe 422 (#59). Planned: `appearance.beauty_direction` / `hair_style` / `makeup_style` / `expression`, `character_version`, `product_id`, `*_profile_id` names, refusing technical fields, `selection`. | #59; planned AC-7 |
| 8 | Admin Promotion Workflow: IN_DEVELOPMENT → VALIDATION → APPROVED → PRODUCTION, recording `validated_by`, `validated_at`, `promoted_by`, `promoted_at`, `qa_notes`, `runtime_profile` ("why it entered Production and what runtime config was approved") | **Partly done.** The lifecycle (as REGISTERED → VALIDATING → VALIDATED → PROMOTED), register / validate / promote / retire, `validated_by` / `validated_at` / `promoted_by` / `promoted_at` and the audit log exist (#55, #57). Planned: `qa_notes` (required at promote), the approved runtime snapshot frozen on the record, definition status synced on promote. | #55, #57; planned AC-2 (columns), AC-8 |
| 9 | Frontend Integration Contract: Hair, Makeup, Expression and Beauty Direction render entirely from API results, with no frontend deploy when a new style is promoted | **Partly in review.** `/styling-options` already returns promoted options with label, thumbnail, group, default and recommended (#59), so a promoted style appears without a backend or frontend code change today. Planned: the written contract (section 2.3), `/appearance` and `/beauty-directions` as its routes, a contract test, and the frontend dropping hard-coded ids and prefix stripping. | #59; planned AC-6, AC-9 |
| 10 | End to end | **Planned, blocked.** Eliska + Quiet Luxury + Low Chignon + Polished Nude + an approved standing pose + one test garment + controlled studio, through API → resolvers → job → Celery/Redis → AI worker → result → QA → review. Needs the AI worker input contract and endpoint from Aryan, and staging (section 6, blocker 1). | planned AC-10 |

The P2 items (recommendation logic, fallback/compatibility, QA automation) have no phase of their
own. They extend phases 5 and 6 and land as AC-11.

Related but separate: #56 (merged) removed strength/seed/workflow fields from Rosanne responses
(`DESIGN.md` gap 12).

## 6. Blockers and decisions needed

| # | Topic | Needed from | Blocks | My recommendation |
|---|---|---|---|---|
| 1 | **⚠ Current generations are not identity-locked.** `run_production` sends the AI worker no reference images, no adapter and no product image (section 4.3). We need: <ul><li>the worker's input contract for reference images, adapter + strength, product image and appearance;</li><li>the staging worker endpoint (ComfyUI / RunPod URL);</li><li>a staging environment with its own Postgres, Redis and storage (`COMFYUI_MOCK_MODE` defaults to on).</li></ul> | **Aryan** (AI worker); Indra for the staging environment | AC-5 worker input, AC-10, and every customer generation's identity | Agree the contract before AC-5 starts. Use a staging deploy of the API + worker, never production. |
| 2 | **APPROVED visibility.** Do customers also see `APPROVED` (= our `VALIDATED`) capabilities? | Shahida | AC-6 | No. Promoted only, as `DESIGN.md` section 0. If yes, they'd need a "preview" flag and dispatch must still refuse them. |
| 3 | **Automatic retry at 0.6 after an identity QA failure.** Enable it, and when? <ul><li>Each retry is a full extra generation (GPU time, and a longer wait).</li><li>Is the retry charged to the customer or absorbed?</li><li>Retry once, or more?</li></ul> | Shahida | AC-11 (the policy flag exists from AC-1, default off) | Keep it off until the cost per production is measured on staging, then decide. Admins can re-run at 0.6 by hand meanwhile. |
| 4 | **Hair list.** <ul><li>Is `HAIR_DOWN` different from `CANONICAL` (canonical is straight, worn down)?</li><li>Are `SLEEK_LOW_BUN` and `LOW_CHIGNON` both needed?</li><li>Does `CANONICAL` keep the customer id `hair_canonical`? It's already promoted; renaming it means a new capability.</li></ul> | Shahida, Aryan | AC-3 | Keep `hair_canonical`. Drop `HAIR_DOWN` if it equals `CANONICAL`. |
| 5 | **Expressions.** `QUIET_LUXURY` recommends `SOFT_CONFIDENCE`, which isn't in any seed list. Which expressions are seeded? | Shahida | AC-3 | Seed `SOFT_CONFIDENCE` at validation stage. Add others only when a direction needs them. |
| 6 | **Recommended defaults** of `CANONICAL_CONTROL`, `LUXURY_WAVES`, `RUNWAY_EDITORIAL`, `CLASSIC_EVENING` and `MODERN_MINIMAL` (only `QUIET_LUXURY` is given). | Shahida | AC-3 | `CANONICAL_CONTROL` = `CANONICAL` + `NATURAL` + `NEUTRAL_EDITORIAL`; the others from Shahida. |
| 7 | **Grooming.** What is "recommended grooming"? It's not one of the six types. Is it `NAILS`, a new `GROOMING` type, or later? | Shahida | AC-2 FK category, AC-6 `grooming_id` | Keep the column and `grooming_id: null` until it's defined. |
| 8 | **The `EE-F-002_CK0750` adapter.** <ul><li>May an `EVALUATION` adapter be used for admin **validation** generations?</li><li>What must it pass to become `PRODUCTION` (`DESIGN.md` question 11)?</li><li>Which capabilities need `REFERENCE_PLUS_ADAPTER`?</li></ul> | Shahida, Aryan | AC-1, AC-8, Phase 10 if the E2E uses the adapter | EVALUATION adapters only in admin validation runs, never in customer productions. The E2E can run `REFERENCE_ONLY` if the adapter isn't promoted yet. |
| 9 | **Silent fallback.** When a chosen capability isn't usable at resolve time, or fails identity QA, may the system swap in `fallback_capability_id` (e.g. `LOW_CHIGNON → CANONICAL`)? | Shahida | AC-5, AC-11 | No silent swap. At resolve time return 503 (nothing charged). At QA time, mark the output for review; `fallback_capability_id` is offered to the customer as a suggestion. |
| 10 | **Field names.** Shahida's request uses camelCase (`characterId`, `hairStyles`); every route we have is snake_case. | Shahida, Indra (frontend) | AC-6, AC-7 | Use snake_case. The frontend already sends snake_case to dispatch. |
| 11 | **Railway / #58.** Merging #58 needs a production backup, P0 (`SELECT version_num FROM alembic_version`) shared, P2/P3/P4 returning 0 rows and P6 returning 0 rows (P1/P5 informational). Every new migration here depends on migrations running on deploy. | Indra | everything after #60 | No change: #58 → #59 → #60, then AC-1. |
| 12 | **One lifecycle.** Should promote/retire of a capability record also move the appearance definition to `PRODUCTION` / `ARCHIVED` (section 1.2)? | Shahida | AC-8 | Yes. |
| 13 | **Reference set roles and seed matching** (from #60) | Aryan, Shahida | promoting `EE-F-002_V1.0_REF_V1`, so AC-5 and Phase 10 | — |
| 14 | **Four-eyes rule** (validator ≠ promoter, `DESIGN.md` question 7) | Shahida | AC-8 (optional) | Still not enforced. |

## 7. Revised implementation PR order

No code until #58, #59 and #60 are merged, in that order. After #60, `alembic heads` is
`reference_sets_001`. Each PR below is small, additive, and runs the full Docker suite serial and
`-n auto` with 0 failed and 0 xfailed.

- **Migration PRs** branch from `main` once the PR before them is merged. If they have to start
  earlier, they stack on the previous migration branch with the PR base set to it, as #60 does on #59.
  That keeps one alembic head: `reference_sets_001 → runtime_profiles_001 →
  appearance_capabilities_001 → production_selection_001`.
- **PRs without a migration** branch from `main` once the PRs they read from are merged.

| PR | Phase(s) | Priority | Migration | Branch / stacks on | Content | Old `DESIGN.md` 8 |
|---|---|---|---|---|---|---|
| **AC-1** Runtime profiles + adapter evaluation | 1, 2, 6 | P0 | **`runtime_profiles_001`** (down: `reference_sets_001`) | `feat/runtime-profiles` from main after #60 (or stacked on `feat/reference-sets`) | `runtime_profiles` table, model, guards, admin API, audit; `EVALUATION` adapter status + admin status endpoint; register `EE-F-002_CK0750` at EVALUATION; seed `EE-F-002_V1.0_RT_V1` as DRAFT (`REFERENCE_ONLY` only). Tests: no strength constant in code, frozen once PRODUCTION, one PRODUCTION per version. | part of 5 |
| **AC-2** Appearance capability schema | 1, 2 | P0 | **`appearance_capabilities_001`** (down: `runtime_profiles_001`) | `feat/appearance-capabilities`, stacked on `feat/runtime-profiles` | `appearance_options` runtime columns, `beauty_directions`, `capability_compatibility`, `qa_profiles` columns, `capability_validations.qa_notes` / `runtime_profile`, `NAILS` capability type, admin create/patch fields, beauty direction defaults endpoint. Tests: Character rows byte-identical, FK category rules, migration parity/re-run/downgrade, the old migrations' guard pattern. | part of 6 |
| **AC-3** Phase 3 seed | 3 | P0 | none (admin seed action) | from main after AC-2 | `POST /admin/characters/EE-F-002/appearance/seed`. <ul><li>**Beauty directions:** `CANONICAL_CONTROL`, `QUIET_LUXURY`, `LUXURY_WAVES`, `RUNWAY_EDITORIAL`, `CLASSIC_EVENING`, `MODERN_MINIMAL`.</li><li>**Hair:** `LOW_CHIGNON`, `SOFT_WAVES`, `SLICK_BACK`, `POLISHED_UPDO`, `HAIR_DOWN` at VALIDATION / VALIDATING; `SLEEK_LOW_BUN`, `PONYTAIL`, `WET_LOOK` at IN_DEVELOPMENT / REGISTERED.</li><li>**Makeup:** `POLISHED_NUDE`, `BRONZED_LUXURY`, `EDITORIAL`, `CLASSIC_EVENING`, `MODERN_MINIMAL` at validation stage; `SOFT_GLAM` in development.</li><li>**Defaults:** `QUIET_LUXURY` → `LOW_CHIGNON` + `POLISHED_NUDE` + `SOFT_CONFIDENCE`.</li><li>**Already promoted:** `CANONICAL` and `NATURAL` stay PROMOTED and aren't touched (insert-only).</li></ul> Never promotes; idempotent. Tests: nothing customer-visible changes. | part of 6 |
| **AC-4** CapabilityResolver | 5 | P0 | none | from main after AC-2 (parallel with AC-3) | `capability_resolver.py` (section 4.2), admin `/resolve` dry run; `customer_options` uses it. Tests: each question × each status, adapter gate, fallback must be production-ready. | — |
| **AC-5** Runtime resolver strategy | 6 | P0 | none (the plan is JSON on the existing `productions.runtime_profile`) | from main after AC-4 | Section 4.3 steps 2–12 and the admin plan dry run; worker input gains reference set + adapter + product image (contract from Aryan, blocker 1). Tests: EVALUATION / EXPERIMENTAL never in a plan, strength only from data, no silent fallback, plan never in a customer response, hash failure is a 503. | 5 |
| **AC-6** Read APIs | 4 | P1 | none | from main after AC-3 | `/appearance`, `/beauty-directions`, `/capabilities` `appearance_types`, admin `/appearance?status=`; `/styling-options` kept. Tests: promoted only, `recommended_defaults` all promoted, `grooming_id` key present, forbidden terms. | 6, 7 |
| **AC-7** Generation request | 7 | P1 | **`production_selection_001`** (down: `appearance_capabilities_001`) | `feat/generation-request` from main after AC-5 | Section 4.1 fields with old aliases, technical fields refused with 422, `productions.selection`. Tests: full validation matrix, beauty-direction defaults/overrides, idempotency. | 11 (partly) |
| **AC-8** Promotion record | 8 | P1 | none (columns from AC-2) | from main after AC-5 | Promote requires `qa_notes`, builds and freezes the runtime snapshot, refuses unsatisfiable strategies, syncs the definition status (blocker 12). Tests: snapshot frozen, audit, 409 cases. | 2 (extension) |
| **AC-9** Frontend integration contract | 9 | P1 | none | from main after AC-6 | Section 2.3 as a tested contract: an OpenAPI snapshot test for `/appearance` and `/beauty-directions`; a test that registers → validates → promotes a new hair style and sees it in `/appearance` with no code change; ids returned unchanged by dispatch. Frontend handover (Indra): render from the API only, send ids back unchanged, fall back on 404. | — |
| **AC-10** End to end | 10 | P1 for the run | none | from main after AC-7 + AC-8 | Admin runbook + a test-mode E2E test (mock worker in CI). A staging run with the real worker: Eliska + Quiet Luxury + Low Chignon + Polished Nude + approved standing pose + one test garment + controlled studio. Needs blockers 1 and 8 and the reference set promoted. Never against production. | — |
| **AC-11** Recommendation, fallback, compatibility, QA | P2 items (extend 5, 6) | P2 | none (tables from AC-2) | from main after AC-8 and AC-10 | Compatibility rules in the resolver and admin API; the automatic retry at the fallback strength behind `fallback_retry_enabled` (stays off unless blocker 3 decides otherwise); per-capability QA profiles in scoring; fallback suggestions. | — |

Then the rest of `DESIGN.md` section 8, unchanged in substance:
- poses by group + `dress` (8);
- camera options (9), needed before `camera_profile_id` accepts values;
- scene / lighting / campaign endpoints (10);
- progress stages (12);
- outputs + review actions (13);
- legacy cleanup (14), including freezing `character_runtime_profiles` / `character_runtime_v2`
  strength fields.

`DESIGN.md` PR 7 (`/style-options`) is replaced by `/appearance` (AC-6).
