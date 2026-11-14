# AI worker input contract (proposal)

Status: **proposal, updated with Aryan's review of #62** (2026-10-27; confirmed facts 2026-10-24;
first draft 2026-10-23).
Docs only: no code, migrations or settings change with this document, and it contains no secrets.
Section 0 lists what Aryan has confirmed, and section 0.1 what his review of #62 changed. Every
point still to be agreed is marked **[to confirm with Aryan]** (or with whoever owns it) and
collected in section 3, "Open items".

This is blocker 1 in `APPEARANCE_STATUS.md` section 6, "current generations are not
identity-locked". It is the input contract AC-5 (strategy in the resolver) needs before it can
start. File references are to `backend/` on `main`.

## 0. Confirmed by Aryan (2026-10-24)

1. **Reference arrangement (tested).** Three images, in this order:
   1. **Image 1, `body_full_front`:** the corrected, approved full-body front of the locked
      character. It is the reference for body proportions and for pose/framing.
   2. **Image 2, `face_golden_crop`:** the golden face crop. It is the facial reference.
   3. **Image 3, `product`:** the product image. It is the garment reference.

   The order is part of the contract (section 2.2).
2. **Strategy.**
   - **Reference-only is the default**, with no active adapter.
   - **The 750-step adapter (`EE-F-002_CK0750`) at 0.4** is optional assistance. It is used only
     when a tested condition benefits from it.
   - **0.6** is a stronger fallback / evaluation setting, and it comes with watch items.
   - **Neither is ever applied automatically to every job.** An adapter is used only when the plan
     says so, from data (runtime profile or promoted capability). The automatic retry at 0.6 stays
     off (`APPEARANCE_STATUS.md` blocker 3).
3. **Runtime: ComfyUI.** Aryan will share the workflow JSON. The node mapping (section 2.10) waits
   for it.
4. **Still open:**
   - There is no staging worker endpoint yet.
   - Automated QA scores are not validated yet.

   Both stay open until deployment and the result / QA format are agreed (section 3).

## 0.1 Aryan's review of #62 (2026-10-27)

Aryan reviewed this contract against the ComfyUI workflow he supplied (PR #62 comment). The
reference order and the strategy in section 0 are unchanged. His points, and where each is now in
this document:

1. **Pose control is unsupported on this route.** The current graph has no OpenPose / ControlNet
   conditioning, so no pose selection is sent to this route (section 2.9).
2. **Output size is "as produced by the workflow".** The graph's latent sizing is driven by the
   references, and 1600 × 2000 was only an illustration. Requested dimensions are never met by
   stretching or resizing the result (section 2.2, "Output size").
3. **The callback example is PARTIAL.** Two delivered and two failed outputs is `PARTIAL`, not
   `COMPLETED`. The example is fixed and PARTIAL is defined (section 2.3).
4. **Errors and storage.** `PRODUCT_HASH_MISMATCH` and `PRODUCT_DOWNLOAD_FAILED` are separate codes
   (section 2.4). Output storage keys include the attempt number, so a rerun keeps the earlier
   outputs (section 2.2).
5. **QA.** Automated thresholds, including the 94.0 identity example, stay disabled until they are
   validated. Every output goes to manual review (section 2.2, `qa`).
6. **Input roles per route and version.** Each workflow route / version declares the input roles it
   needs. The Front-based route stays unchanged for the first staging test. A separate, versioned,
   **experimental** pose-based route is documented, with its own `pose_base` role (section 2.8).
7. **Still open:**
   - deployment ownership;
   - the staging endpoint;
   - runtime limits;
   - retention.

   The workflow JSON and the node mapping are documented in section 2.10 (package r02, 27 Oct 2026).
   Backend asset IDs are still open.

## 1. What is sent to the worker today

### 1.1 Path

1. **Dispatch.** `POST /api/v1/productions/dispatch` → `production_dispatch.dispatch`
   (`app/services/production_dispatch.py:395`):
   1. It resolves the request into the admin-only Runtime Character Profile
      (`resolve_runtime_profile`, `:269`) and stores it on `productions.runtime_profile`.
   2. It creates an `ai_jobs` row (`job_type = "production"`, `inputs = {"production_id": …}`) and
      reserves credits.
   3. It enqueues the job (`enqueue`, `:109`): `process_production_job.delay(job_id)` (`:112`).
2. **Celery task.** `app.worker.process_production_job` (`app/worker.py:882`), with
   `max_retries=0` ("credits are finalized or refunded exactly once"). It opens a DB session and
   calls `run_production(db, job_id)` (`production_dispatch.py:503`).
3. **`run_production`.** It skips the job unless it is `queued` / `pending`, sets it to
   `processing`, then calls `_comfyui` (`:520`). That loops `count` times (`:530`), one ComfyUI
   prompt per image, **one after another**, each through `GenerationJobManager.run_with_timeout`
   (`app/services/generation_pipeline.py:125`).
4. **Pipeline** (`_run_generation`, `generation_pipeline.py:144`).
   1. It takes a hard-coded base workflow (`_get_base_workflow`, `:192`) and injects inputs by
      node id (`GenerationInputBuilder.build`).
   2. It submits the workflow, waits for completion, and downloads the **first** output image only
      (`:181`).
5. **ComfyUI client** (`app/services/comfyui_service.py`), with base URL `settings.COMFYUI_URL`
   (default `http://localhost:8188`). No auth header is sent, and each HTTP call has a 30 s
   timeout (`COMFYUI_TIMEOUT`, `:12`):
   - `POST {COMFYUI_URL}/prompt` with body `{"prompt": <workflow>, "client_id": <uuid4>}` returns
     `prompt_id` (`:93`).
   - The client waits on `ws(s)://…/ws?clientId=<client_id>` for up to 300 s (`:146`, `:163`).
     Without the `websockets` package it polls `GET {COMFYUI_URL}/history/{prompt_id}` every 2 s,
     up to 150 times (`:111`–`:113`).
   - The image comes from `GET {COMFYUI_URL}/view?filename=<name>&type=output` (`:213`).
6. **Results.** Each image's bytes are saved by `register_output_asset` (`generation_pipeline.py:220`):
   - via `storage_service.save_file_bytes`, as `generation_<job>_<timestamp>_<hex8>.png`;
   - stored at `s3://<bucket>/<key>`, or `/uploads/<key>` with local storage;
   - registered as a brand `assets` row with `meta = {source, job_id, job_type, production_id}`.

   Then `job.outputs = {"images": [{"asset_id": …}]}`, the job is `completed`, and the credits are
   finalized (`production_dispatch.py:544`). Any exception sets the job `failed` and refunds once
   (`:551`). No hash of an output is recorded.

### 1.2 The exact worker input today

`run_production` builds this and nothing else (`production_dispatch.py:520`–`:528`):

```json
{
  "scene_description": "<location display_name>, <lighting preset_key>",
  "pose_filename": "<pose control_reference.asset_url, or null>",
  "aspect_ratio": "4:5",
  "resolution": "2K"
}
```

It is injected into this base workflow (`generation_pipeline.py:192`):

| node | class | input set |
|---|---|---|
| `14` | `CLIPTextEncode` (positive prompt) | `text` = `scene_description` |
| `7` | `CLIPTextEncode` (negative prompt) | `text` stays `"blurry, low quality"` (nothing is injected) |
| `22` | `LoadImage` (pose reference) | `image` = `pose_filename` |

`aspect_ratio` and `resolution` are passed to the builder but no node receives them. `extra_inputs`
is never used by `run_production`.

### 1.3 What is not sent (why generations aren't identity-locked)

| In the resolved profile | Sent to the worker? |
|---|---|
| Reference images of the locked character (and, from #60, the hashed reference set) | **no** |
| Adapter and strength (identity, appearance, pose, product layers) | **no** |
| Product image (`layers.product.storage_path`) | **no** |
| Appearance (hair, makeup, expression) | **no** |
| Body core (178 cm, stature, archetype) | **no** |
| Camera (`focal_length_mm`) and lighting `workflow_params` | **no** (only the lighting key, as prompt text) |
| `params.seed` (generated at `:357`) and `quality` | **no** |
| Workflow route / provider route from the capability pack | **no**: the hard-coded base workflow is always used |

### 1.4 Other findings on this path

These affect the contract, and AC-5 should fix them:

1. **No real model graph.** The base workflow has no checkpoint loader, sampler or output node, and
   node `14` references node `4`, which isn't in the prompt. A real ComfyUI would reject it; only
   mock mode produces images.
2. **Mock mode is the default.** `COMFYUI_MOCK_MODE` defaults to on (`app/config.py:135`), and in
   that mode a 1×1 PNG is returned per image. In production this is only a warning
   (`app/config_production.py:112`), not fatal.
3. **The pose image isn't a file ComfyUI has.** `pose_filename` is a URL or storage path put into
   `LoadImage.image`, which expects a file name already in ComfyUI's input folder. Nothing uploads
   it.
4. **The production task may never be consumed.**
   - `process_production_job` has no entry in `task_routes` (`app/worker.py:54`), so Celery routes
     it to the default queue `celery`.
   - A worker started as in `docker-compose.yml:69` and `kubernetes/deployments.yaml:86` (no `-Q`)
     consumes only `default`, `high_priority` and `processing`. I checked both in the API image:
     the route resolves to `celery`, and a fresh process's queues don't include it.
   - **Fix in review: #63** routes every task to a consumed queue (`process_production_job` →
     `processing`) and sets `task_default_queue = "default"`.
   - The Railway worker command isn't in the repo **[to confirm with Indra]**.
5. **The time limit is shorter than the work.**
   - Celery's `task_time_limit` is 300 s (`app/worker.py:46`) with `acks_late`, but one image may
     take up to 600 s (`JOB_TIMEOUT_SECONDS`), and `count` images run one after another.
   - A hard kill at 300 s leaves the job `processing` with credits still reserved. Nothing sweeps
     stale productions.
6. **Customers get a storage path, not a URL.** Output URLs returned to customers are the raw
   `storage_path` (`customer_outputs`, `production_dispatch.py:487`); with S3 that's `s3://…`, which
   a browser can't load. This is outside this contract but on the same path.

## 2. Proposed contract

### 2.1 Shape of the exchange

Proposal: **submit and call back.** The API never holds a Celery task open for a whole GPU run.

```
API (Celery task, short)           AI worker (GPU)                     API (callback route)
  build job from the plan  ──POST /v1/jobs──►  validate, fetch refs/adapter
  status = submitted       ◄── 202 {job_id} ─  generate N outputs
                                               upload each output via presigned PUT
                                               ──POST callback (signed)──►  verify, register assets,
                                                                            QA, finalize/refund once
  sweeper: past deadline and no callback → GET /v1/jobs/{id}; still nothing → fail + refund once
```

- **Runtime: ComfyUI (confirmed).** The payload below is what the API sends. A thin wrapper next to
  ComfyUI maps it onto Aryan's workflow JSON and submits it to ComfyUI's own `/prompt` API. The API
  stops building or sending a graph.
- **Transport: HTTPS JSON**, contract version `2026-11.v1`. These points are
  **[to confirm with Aryan]**:
  - who runs the wrapper;
  - where it is hosted (a GPU host, or a RunPod serverless endpoint with `/run` + `/status`);
  - the staging endpoint, which doesn't exist yet.

  The payload fits any of these hosts; only the envelope changes.
- **Worker API (proposed):**
  - `POST /v1/jobs` (submit);
  - `GET /v1/jobs/{job_id}` (status, for reconciliation);
  - `POST /v1/jobs/{job_id}/cancel`.
- **Auth.**
  - **API → worker:** a bearer token (`AI_WORKER_TOKEN`).
  - **Worker → API callback:** an HMAC-SHA256 signature over the raw body in
    `X-Worker-Signature`, with a timestamp header that is rejected after 5 minutes. It's signed with
    `AI_WORKER_CALLBACK_SECRET`.

  These are new settings, named only; no values here. The existing
  `X-Internal-Secret` callbacks (`app/routers/internal_callbacks.py`) are the precedent, but a
  per-request signature is safer for a third-party host. **[to confirm with Aryan]**
- **Files never travel inline.** The worker gets short-lived presigned GET URLs for every input and
  presigned PUT URLs for every output. It never gets S3 or database credentials. That's the pattern
  already used for FASHN (`app/services/fashn_catalog.py:67`, `storage_service.presigned_get_url`;
  the TTL is a setting, as `FASHN_INPUT_URL_TTL_SECONDS` is). Presigned URLs are never logged or
  stored by either side.

### 2.2 Submit payload

`POST /v1/jobs`. Example: Eliska, Quiet Luxury (Low Chignon + Polished Nude + Soft Confidence),
standing pose, a garment, white studio, `REFERENCE_ONLY`.
Canonical asset ids, the workflow route name and the descriptors are illustrative. No workflow
route is seeded today. Following Aryan's review, the example has no pose block and no output
pixel size, uses attempt-numbered upload keys, and has automated QA gates off.

```json
{
  "contract_version": "2026-11.v1",
  "job_id": "prd_7f3a9c1e2b0d4c5e8a9b1c2d3e4f5a6b",
  "attempt": 1,
  "submitted_at": "2026-11-10T10:12:00Z",
  "deadline_at": "2026-11-10T10:32:00Z",

  "character": {
    "character_id": "EE-F-002",
    "character_version": "1.0",
    "locked": true,
    "body": { "canonical_height_cm": 178.0, "stature": "TALL", "body_archetype": "HIGH_FASHION_RUNWAY_SLIM" }
  },

  "runtime": {
    "runtime_profile_id": "EE-F-002_V1.0_RT_V1",
    "runtime_profile_version": 1,
    "strategy": "REFERENCE_ONLY",
    "workflow": { "route": "GARMENT_V1", "version": "1",
                  "input_roles": ["body_full_front", "face_golden_crop", "product"] }
  },

  "references": {
    "reference_set_id": "EE-F-002_V1.0_REF_V1",
    "content_hash": "<sha256 of the ordered (asset_id, sha256) pairs of the reference set items>",
    "images": [
      { "order": 1, "role": "body_full_front", "source": "reference_set", "asset_id": "EE-F-002_V1.0_CAN_010",
        "url": "<presigned GET>", "sha256": "<64 hex>", "mime": "image/png", "width": 1536, "height": 2048 },
      { "order": 2, "role": "face_golden_crop", "source": "reference_set", "asset_id": "EE-F-002_V1.0_CAN_001",
        "url": "<presigned GET>", "sha256": "<64 hex>", "mime": "image/png", "width": 1024, "height": 1024 },
      { "order": 3, "role": "product", "source": "product", "asset_id": null,
        "url": "<presigned GET>", "sha256": "<64 hex>", "mime": "image/jpeg" }
    ]
  },

  "adapter": null,

  "product": {
    "product_type": "garment",
    "reference_role": "product"
  },

  "appearance": {
    "beauty_direction": { "key": "QUIET_LUXURY", "version": 1 },
    "hair": { "key": "LOW_CHIGNON", "version": 1,
              "descriptor": "low smooth chignon at the nape, center part, no flyaways" },
    "makeup": { "key": "POLISHED_NUDE", "version": 1,
                "descriptor": "refined nude tones, satin skin, defined brows, nude lip" },
    "expression": { "key": "SOFT_CONFIDENCE", "version": 1,
                    "descriptor": "relaxed jaw, soft eyes, closed-mouth hint of a smile" },
    "grooming": null
  },

  "pose": null,

  "camera": { "shot": "full_body", "focal_length_mm": 85, "aspect_ratio": "4:5", "height": "eye", "angle": "front" },

  "scene": {
    "env_id": "ENV-STU-0001", "family": "STUDIO",
    "descriptor": "white seamless studio, clean floor bounce",
    "lighting": { "preset_id": "STUDIO_SOFT_DIFFUSE", "params": { "...": "lighting workflow_params" } }
  },

  "output": {
    "count": 4, "size": "AS_PRODUCED", "format": "png",
    "seed": 123456789, "seed_policy": "increment_per_output",
    "uploads": [
      { "index": 0, "url": "<presigned PUT>", "key": "productions/prd_7f3a…/attempt_1/0.png" },
      { "index": 1, "url": "<presigned PUT>", "key": "productions/prd_7f3a…/attempt_1/1.png" },
      { "index": 2, "url": "<presigned PUT>", "key": "productions/prd_7f3a…/attempt_1/2.png" },
      { "index": 3, "url": "<presigned PUT>", "key": "productions/prd_7f3a…/attempt_1/3.png" }
    ]
  },

  "qa": {
    "profile_ids": ["QA-PROFILE-CATALOG-001", "QA-PROFILE-APPEARANCE-HAIR-001"],
    "automated_gates": "DISABLED",
    "review": "MANUAL_ALL",
    "identity_hard_gate": null,
    "scored_by": "api",
    "fallback_retry": { "enabled": false }
  },

  "callback": { "url": "https://api.modelens.ai/api/v1/internal/worker/jobs/prd_7f3a…/result",
                "signature": "hmac-sha256" }
}
```

**Reference order (confirmed by Aryan).** On the Front-based route (`GARMENT_V1`),
`references.images` always has exactly these three entries, in this order. The worker feeds them to
the workflow in `order`, and the API never reorders or adds images. Other routes declare their own
roles (section 2.8):

| `order` | `role` | `source` | What it is | Used for |
|---|---|---|---|---|
| 1 | `body_full_front` | `reference_set` | the corrected, approved full-body front of the locked character | body proportions, pose and framing |
| 2 | `face_golden_crop` | `reference_set` | the golden face crop | face identity |
| 3 | `product` | `product` | the brand's product image for this production (`productions.product_asset_id`) | garment |

- **Images 1 and 2** are the items of the PRODUCTION reference set, and `content_hash` covers only
  those two.
- **Image 3** is per production, so it is not part of the reference set or its hash. Its sha256 is
  computed by the API when the job is built.
- A job that can't fill all three roles is refused by the API before anything is charged (503 for
  the reference set, 422 for a missing product). It is never sent with fewer images.
- The roles sent are exactly the route's declared `runtime.workflow.input_roles`, in that order
  (section 2.8).

**Default: no adapter (confirmed by Aryan).** `adapter` is `null` and the strategy is
`REFERENCE_ONLY` unless the plan says otherwise. The plan says otherwise only when one of these
selects `REFERENCE_PLUS_ADAPTER`:
- the PRODUCTION runtime profile;
- or a promoted capability whose tested condition benefits from the adapter.

That decision is data, never a worker default, and the adapter is never added to every job.

With `REFERENCE_PLUS_ADAPTER`, `adapter` is set. `strength` is 0.4, the optional assistance
setting. `fallback_strength` is 0.6, the stronger fallback / evaluation setting with watch items.
0.6 is used only for an admin re-run or evaluation, or by the retry policy once it is enabled. It
is off today, so it is never used automatically.

```json
"adapter": {
  "adapter_id": "EE-F-002_CK0750",
  "layer": "IDENTITY",
  "sha256": "<64 hex, model_artifacts.checksum_sha256>",
  "source": { "kind": "worker_store", "path": "<worker-side model path>" },
  "strength": 0.4,
  "fallback_strength": 0.6
}
```

**Output size: as produced by the workflow.** The supplied graph sizes its latent from the
references, and no output resolution has been validated yet. Until one is:
- the API sends no pixel size (`output.size = "AS_PRODUCED"`);
- the worker reports the actual `width` / `height` of each output in the callback;
- neither side ever meets a requested size or aspect ratio by stretching, resizing, cropping or
  padding the result.

Once a resolution is validated for a route / version, it is declared with that route, and the
payload gains explicit `width` / `height` for it.

Field rules:

| Field | Source (after AC-1…AC-5) | Rules | Open |
|---|---|---|---|
| `job_id` | `productions.production_id` | the worker's idempotency key, together with `attempt` | |
| `attempt` | starts at 1 | a new attempt only from an admin re-run or the retry policy, never from transport retries | |
| `deadline_at` | submit time + job timeout (setting) | the worker stops and reports `TIMEOUT` after it | value **[to confirm with Aryan]** |
| `character.*` | current LOCKED `character_registry_versions` row | informational for the worker; identity comes from `references` | |
| `runtime.strategy` | resolver step 8 | `REFERENCE_ONLY` or `REFERENCE_PLUS_ADAPTER` | |
| `runtime.workflow` | the capability pack's `workflow_route` / `workflow_version`; `input_roles` from that route / version's declaration (section 2.8) | the ComfyUI wrapper maps the route to Aryan's workflow JSON (confirmed: ComfyUI); **we stop sending a graph**. The worker checks `input_roles` against its own definition of the route / version and fails with `INVALID_INPUT` on a difference | route names; node mapping for Images 1–3, the adapter and the seed: see section 2.10 |
| `references.images[]` | Images 1–2: the PRODUCTION reference set (#60, roles as proposed in section 2.7). Image 3: the dispatch's product asset | **confirmed:** exactly `body_full_front`, `face_golden_crop`, `product`, in that order. The worker checks each file's sha256 before use and fails with `REFERENCE_HASH_MISMATCH` otherwise. For Image 3, a failed download is `PRODUCT_DOWNLOAD_FAILED` and a wrong sha256 is `PRODUCT_HASH_MISMATCH` | size / format limits per image, and the crop spec of `face_golden_crop` (size, margin, background) **[to confirm with Aryan]** |
| `adapter` | runtime profile / promoted capability snapshot; `PRODUCTION` only | **confirmed:** `null` by default (reference-only). 0.4 only when a tested condition benefits; 0.6 is fallback / evaluation only; never automatic on every job. Strengths come only from data, never a worker default | which tested conditions benefit, and the 0.6 watch items; whether the worker loads adapters from its own store by id + sha256 or downloads them; which ComfyUI node and input(s) "strength" sets (e.g. LoRA model / clip strength) **[to confirm with Aryan]** |
| `product` | `product_type` from the dispatch; the image is `references.images[2]` (role `product`) | presigned GET, sha256 computed by the API | whether the worker needs a mask, or a flat-lay vs on-model image; max size **[to confirm with Aryan]** |
| `appearance.*.descriptor` | new admin-only field on `appearance_options` (planned with AC-2) | **internal descriptors, never customer labels**; `grooming` stays `null` until defined | descriptor format (prompt text, structured tags, or a reference image per style) **[to confirm with Aryan]** |
| `pose` | none on `GARMENT_V1` | **`null`. Pose control is UNSUPPORTED on this route** (no OpenPose / ControlNet in the graph). The worker rejects a non-null `pose` with `INVALID_INPUT`, and never silently ignores it (section 2.9) | what dispatch does when a customer picks a pose for this route: **decision open** (section 2.9) |
| `camera` | `focal_length_mm` / `aspect_ratio` today; shot/height/angle once camera options exist | `aspect_ratio` is never applied by stretching, resizing or cropping the result (see "Output size") | how the worker applies focal length; whether the graph can honour an aspect ratio at all **[to confirm with Aryan]**; what dispatch does with a customer's aspect ratio meanwhile: **decision open** (section 3.2) |
| `scene` | the location and lighting presets' `technical_config` | `descriptor` is internal text, not the customer label | |
| `output.size` | `AS_PRODUCED` until a resolution is validated for the route / version | **no pixel size is sent**; the callback reports the actual size; the result is never resized to a requested size. The aspect ratio × resolution table (`app/services/production_presets.py`) is not used for this route | a validated resolution per route / version **[to confirm with Aryan]** |
| `output.seed` | `params.seed` (already generated) | output *i* uses `seed + i` | whether seeds are reproducible on the worker **[to confirm with Aryan]** |
| `output.uploads[]` | presigned PUT per output to `productions/<production_id>/attempt_<attempt>/<index>.png` | the key includes the attempt, so a rerun (a new `attempt`) never overwrites an earlier attempt's outputs. Within one attempt the key is deterministic, so a duplicate upload overwrites rather than adds | PUT TTL **[to confirm with Aryan]** |
| `qa` | runtime profile + capability QA profiles | `scored_by: api` = the worker only generates. **Automated QA thresholds stay disabled until validated (confirmed in review):** `automated_gates = "DISABLED"` and `review = "MANUAL_ALL"`, so every output goes to manual review and no score passes, fails or retries an output. `identity_hard_gate` is `null`; the earlier 94.0 was an unvalidated example and is not used. Any scores are recorded for information only. `fallback_retry.enabled` mirrors `runtime_profiles.fallback_retry_enabled` (default false) | **open:** the result / QA format, where QA runs (worker or API), which identity metric, and when scores become a gate **[to confirm with Aryan]** |

The worker gets no brand id, user id, customer label, price or credit information.

### 2.3 Results

The worker uploads each output to its presigned PUT URL, then sends one callback per job.

```json
POST /api/v1/internal/worker/jobs/prd_7f3a…/result
X-Worker-Timestamp: 1762769520
X-Worker-Signature: <hex hmac-sha256 of "<timestamp>.<raw body>">

{
  "contract_version": "2026-11.v1",
  "job_id": "prd_7f3a9c1e2b0d4c5e8a9b1c2d3e4f5a6b",
  "attempt": 1,
  "status": "PARTIAL",
  "outputs": [
    { "index": 0, "key": "productions/prd_7f3a…/attempt_1/0.png", "sha256": "<64 hex>",
      "width": "<as produced>", "height": "<as produced>",
      "mime": "image/png", "seed": 123456789, "strength_used": null },
    { "index": 1, "key": "productions/prd_7f3a…/attempt_1/1.png", "sha256": "<64 hex>",
      "width": "<as produced>", "height": "<as produced>",
      "mime": "image/png", "seed": 123456790, "strength_used": null }
  ],
  "failed_outputs": [
    { "index": 2, "error": { "code": "OUT_OF_MEMORY", "message": "…", "retryable": true } },
    { "index": 3, "error": { "code": "OUT_OF_MEMORY", "message": "…", "retryable": true } }
  ],
  "worker": { "worker_version": "…", "workflow_version": "…", "gpu": "…" },
  "timings_ms": { "queue": 4200, "fetch_inputs": 1800, "generate": 61000, "upload": 900 }
}
```

- **`status`** (the example above is `PARTIAL`: outputs 0 and 1 delivered, 2 and 3 failed):
  - `COMPLETED`: all `count` outputs are uploaded, and `failed_outputs` is empty.
  - `PARTIAL`: at least one output is uploaded and at least one failed. Every index from 0 to
    `count - 1` is in exactly one of `outputs` and `failed_outputs`.
  - `FAILED`: nothing usable was produced; the body has one `error`.
  - `CANCELLED`.

  The API decides the final status after its own checks. If an output the worker reported fails
  the API's hash check (`OUTPUT_HASH_MISMATCH`), a `COMPLETED` callback becomes `PARTIAL`, or
  `FAILED` if no output is left.
- **What the API does with a callback:**
  1. It checks the signature, `job_id` and `attempt`.
  2. For each output, it reads the object at `key` and compares its sha256 to the reported one.
     A mismatch makes that output failed (`OUTPUT_HASH_MISMATCH`).
  3. It registers each good output as a brand asset, recording the sha256 in `assets.meta`.
  4. It runs QA.
  5. It finalizes credits for the delivered outputs and refunds the rest once. This uses the
     existing ledger and `lock_reservation`, so a duplicate callback is a no-op.
- **Charging for PARTIAL: a decision for Shahida.** The proposal is to charge only for delivered
  outputs, i.e. those that passed the API's hash check, and refund the rest once against the same
  reservation. Manual review does not change the charge unless Shahida decides otherwise.
  **[to decide: Shahida]**
- **Progress (optional).** `POST …/progress {job_id, attempt, stage, percent}` maps to the
  production stages `PREPARING / GENERATING / FINALIZING` (`DESIGN.md` 4.8). It's
  **[to confirm with Aryan]** whether the worker can report progress.

### 2.4 Error codes

The worker reports a code, a free-text `message` and `retryable`. The API maps codes to
customer-safe text and never passes `message` to a customer.

| Code | Meaning | `retryable` | API action |
|---|---|---|---|
| `INVALID_INPUT` | payload fails the worker's validation | false | fail, refund, admin alert (a bug on our side) |
| `UNSUPPORTED_CONTRACT_VERSION` | worker doesn't know `contract_version` | false | fail, refund, admin alert |
| `REFERENCE_FETCH_FAILED` | a reference URL couldn't be fetched (expired, 403, 404) | true | re-sign the URLs and resubmit the same attempt once |
| `REFERENCE_HASH_MISMATCH` | a reference's sha256 differs | false | fail, refund, **integrity alert** (the reference set may be tampered with) |
| `PRODUCT_DOWNLOAD_FAILED` | the product image couldn't be downloaded (expired URL, 403, 404, network) | true | re-sign and resubmit once |
| `PRODUCT_HASH_MISMATCH` | the product image downloaded, but its sha256 differs from the payload | false | fail, refund, admin alert (the product object changed after the job was built, or is corrupt) |
| `ADAPTER_NOT_FOUND` | the worker doesn't have `adapter_id` | false | fail, refund, admin alert |
| `ADAPTER_HASH_MISMATCH` | the adapter file's sha256 differs | false | fail, refund, integrity alert |
| `WORKFLOW_NOT_FOUND` | unknown `runtime.workflow.route` | false | fail, refund, admin alert |
| `OUT_OF_MEMORY` | GPU OOM | true | per output; see 2.5 |
| `SAFETY_BLOCKED` | the worker's safety filter blocked an output | false | per output; refund it |
| `TIMEOUT` | `deadline_at` passed | false | fail what's left, refund it |
| `UPLOAD_FAILED` | presigned PUT failed | true | re-sign and resubmit once |
| `CANCELLED` | cancelled by `POST /v1/jobs/{id}/cancel` | false | refund |
| `INTERNAL` | anything else | true | see 2.5 |

The codes and the `retryable` flags are **[to confirm with Aryan]**.

### 2.5 Timeouts, retries, idempotency

- **Timeouts.**
  - **Submit:** a 30 s HTTP timeout, same as today's client. The worker answers 202 at once and
    does the work afterwards.
  - **Job:** `deadline_at` = submit + a per-workflow setting. The value is
    **[to confirm with Aryan]**; it depends on images per job and GPU time per image.
  - **Celery:** the API's Celery task only submits, so it stays well under `task_time_limit`. That
    fixes 1.4 item 5.
- **Reconciliation.** A periodic API task (Celery beat, as the existing purges) finds productions
  `submitted` past `deadline_at` + grace with no callback, then asks `GET /v1/jobs/{job_id}`:
  - if the worker has a result, the API processes it like a callback;
  - if the worker says it's still running, the API waits one more grace period;
  - otherwise it fails the production and refunds once.
- **Transport retries.** The API retries submit and the worker retries the callback, both with
  exponential backoff, up to 3 times. The worker treats a repeated `(job_id, attempt)` as the same
  job: it returns the current state and never generates twice. The API treats a repeated callback
  as a no-op once the production is settled.
- **Generation retries.** No automatic re-generation by default. That keeps credits exact and
  compute predictable.
  - A retryable error (`REFERENCE_FETCH_FAILED`, `PRODUCT_DOWNLOAD_FAILED`, `UPLOAD_FAILED`) gets one
    resubmit of the **same** attempt with fresh URLs.
  - `OUT_OF_MEMORY` and `INTERNAL` are reported as failed outputs and refunded.
  - Whether the worker may retry an OOM internally, at the same seed, before reporting is
    **[to confirm with Aryan]**.
  - The identity-QA retry at `fallback_strength` happens only if
    `qa.fallback_retry.enabled` (default false, Shahida's decision, `APPEARANCE_STATUS.md`
    blocker 3). It would be a new `attempt` for the failed outputs only.
- **Idempotency keys.**
  - **Customer → API:** the existing `Idempotency-Key` on dispatch.
  - **API → worker:** `(job_id, attempt)`.
  - **Worker → storage:** the output `key`, which is deterministic per attempt
    (`…/attempt_<attempt>/<index>.png`), so reruns keep their history.
  - **API ledger:** `production_id` with `lock_reservation`.

### 2.6 Security and privacy

- **Secrets and URLs.** No secrets in payloads or logs. Presigned URLs expire in minutes (TTL
  setting) and are never logged or stored on either side.
- **What the worker gets and keeps.** The worker receives only the files it needs. It gets no
  customer identifiers, and it deletes its local copies of inputs and outputs after the callback
  succeeds. The retention period is **[to confirm with Aryan]**.
- **Verification.** Reference and adapter hashes are verified on the worker before generation,
  and output hashes on the API after upload. This gives an end-to-end check that the locked
  identity files were the ones used.
- **Customer responses never contain** strategy, adapter, strength, seed, workflow, worker,
  provider or QA internals (`DESIGN.md` section 0). The plan and the callback body stay admin-only.

### 2.7 Reference roles: how this differs from #60, and the proposed change

**#60 today** (`feat/reference-sets`, in review, not merged):
- **Roles.** `app/services/reference_sets.py` `ROLES` has five: `face_front`, `face_34`, `profile`,
  `body_full`, `body_34`. They were marked "to be confirmed by Aryan/Shahida".
- **Required to lock.** `REQUIRED_ROLES` = `face_front` + `body_full`.
- **Item order.** Items are kept in the order the admin sends them.
- **Seed.** It picks one eligible V1.0 canonical asset per role by framing and angle
  (`SEED_ROLE_MATCH`).

**What Aryan tested** (section 0):
- The character references are two images, in a fixed order: `body_full_front` first, then
  `face_golden_crop`.
- The product is Image 3. It is per production, so it is not part of the reference set.

**The differences:**

| | #60 | Aryan's tested arrangement |
|---|---|---|
| Body reference | `body_full` (any front full body) | `body_full_front`: **the corrected, approved** full-body front |
| Face reference | `face_front` (a front close-up / portrait) | `face_golden_crop`: **the golden face crop** |
| Other roles | `face_34`, `profile`, `body_34` (optional) | not used; their effect isn't tested |
| Required to lock | `face_front` + `body_full` | `body_full_front` + `face_golden_crop` (both, and only these) |
| Order | as sent by the admin | fixed: body first, face second (the worker uses this order) |
| Product | not in the set | Image 3, from the production; not in the set |

**Proposed change to #60** (proposal only; #60 is not changed by this document):
1. **Roles.** `ROLES = ("body_full_front", "face_golden_crop")`, and the router's `Role` literal to
   match. Drop `face_34`, `profile` and `body_34` until a workflow is tested with them. Adding a
   role later is a code change, not a migration: `role` is `varchar(30)`.
2. **Required to lock.** Both roles, exactly one asset each. Lock refuses a set with a missing,
   duplicated or extra role.
3. **Order.** `sort_order` comes from the role order (`body_full_front` = 0, `face_golden_crop` =
   1), not from the request. The set's `content_hash` covers the ordered pairs, so the order is
   locked with the set.
4. **Seed.**
   - Replace the framing/angle matching with the two canonical asset ids Aryan confirms: the
     corrected 178 cm full-body front, and the golden face crop.
   - The seed still only builds and locks `EE-F-002_V1.0_REF_V1`. It never promotes.
   - If the face crop isn't registered as a canonical asset yet, it needs to be registered first,
     with its file and sha256.
5. **Migration and data.** No migration change. No sets exist in production (#60 isn't merged), so
   no data change is needed.
6. **Tests.** Update the role fixtures and the seed tests; add one test that the lock order is
   body, then face.

### 2.8 Input roles per workflow route and version

Each workflow route / version declares the input roles it requires, in order. The API fills
exactly those roles, refuses the job before charging if it can't, and sends them as
`runtime.workflow.input_roles` plus `references.images[]`. The worker checks them against its own
definition of the route / version. Where the API stores the declaration (for example with the
workflow route definition) is an AC-5 implementation choice; no migration is proposed here.

| Route / version (names illustrative) | Status | Image 1 | Image 2 | Image 3 |
|---|---|---|---|---|
| `GARMENT_V1` v1, Front-based | **current; unchanged for the first staging test** | `body_full_front` | `face_golden_crop` | `product` |
| `GARMENT_POSE_BASE_EXP` v1, pose-based | **EXPERIMENTAL; not a production capability** | `pose_base` | `face_golden_crop` | `product` |

**`pose_base` rules (experimental route only):**
- It is an approved, posed image of Eliska (EE-F-002) with its **own asset id and sha256**, sent in
  `references.images[]` with role `pose_base` and checked like any other reference.
- It **never replaces `body_full_front`** and is never labelled as it. `body_full_front` stays the
  locked body authority in the PRODUCTION reference set; a `pose_base` image is not a member of
  that set and doesn't change its `content_hash`.
- Who approves a `pose_base` image, and where it is registered, is open (section 3.2).
- The route is never attached to a PRODUCTION capability pack or offered to customers. It is used
  only for admin or staging experiments, as its own version, until a workflow for it is validated.

### 2.9 Pose control on the Front-based route

The current EE002 graph has no OpenPose / ControlNet conditioning. On `GARMENT_V1`:
- **Pose control is UNSUPPORTED** until a workflow with pose conditioning is validated and
  declared as its own route / version.
- The API sends `"pose": null`: no control image, geometry or pose `workflow_params`. Image 1
  (`body_full_front`) sets pose and framing.
- The worker rejects a non-null `pose` with `INVALID_INPUT`. It never silently ignores it, so a
  customer is never charged for a pose that wasn't applied.

**Decision open: what dispatch does when a customer picks a pose for this route.** Today dispatch
resolves `pose_id` against the poses offered for the product type: `standing`, `walking` and
`editorial` are seeded for garment. Options, not decided here:
1. **Reject before charging.** Dispatch returns 422 for any pose other than the route's single
   supported one.
2. **Offer no choice.** The poses route returns only the supported pose for packs whose route has
   no pose control, and dispatch accepts no other. Indra's #62 comment proposes pinning
   ProductionComposer to Canonical Front for this pack, which fits this option; dispatch would
   still enforce it.
3. Hide the pose step entirely for such packs.

Silently ignoring a chosen pose is not an option. **[to decide: Shahida, with Indra]**

### 2.10 Workflow mapping (EE002_Q21 v01)

Source: 04_RECORDS/NODE_MAPPING.json and 04_RECORDS/INPUT_ASSET_MANIFEST.json (package r02, 27 Oct 2026).
Workflow: 01_WORKFLOW/EE002_Q21_REFERENCE_PLUS_LORA_Reference_v01_API.json (confirm with Aryan).

| Field | Node | Input | Value |
|---|---|---|---|
| body_full_front | 470 | image | from BODY_FRONT.png (sha256 a06fd043…) |
| face_golden_crop | 481 | image | from GOLDEN_FACE.png (sha256 82077595…) |
| product | 491 | image | from BLACK_WRAP_DRESS.png (sha256 b8c1f8d5…) |
| negative_prompt | 459:474 | negative_prompt | "" |
| seed | 459:458 | seed | 42003 |
| steps / cfg | 459:458 | steps / cfg | 25 / 1 |
| sampler / scheduler / denoise | 459:458 | sampler_name / scheduler / denoise | euler / simple / 1 |
| adapter | 459:486 | lora_name / strength_model | modelens__Eliska__EE002_Q21_BASELINE_v01_000000750.safetensors / 0 |
| custom size switch | 459:468 | switch | false (output from TextEncodeQwenImage21 latent) |
| save prefix | 461 | filename_prefix | EE002_PROD02_QUIET_LUXURY_BLACKWRAP_HOTEL_REFONLY_S42003_v02 |

Input rule: do not place presigned URLs in these fields. Download, verify the checksum, upload to worker ComfyUI input storage, then set the image field to the returned local filename.
Open: backend_asset_id is null for all three inputs; registry IDs must be agreed with backend before staging.

## 3. Open items

### 3.1 Resolved (confirmed by Aryan, 2026-10-24)

1. **References.** Three images, in this order: `body_full_front`, `face_golden_crop`, `product`
   (sections 0 and 2.2).
2. **Default strategy.**
   - Reference-only, with no active adapter.
   - The adapter at 0.4 only when a tested condition benefits.
   - 0.6 as the fallback / evaluation setting.
   - Neither automatic on every job.
3. **Runtime.** ComfyUI.

From Aryan's review of #62 (2026-10-27):

4. **Pose control** is UNSUPPORTED on the Front-based route; `pose` is `null` and never silently
   ignored (section 2.9).
5. **Output size** is as produced by the workflow, never stretched or resized (section 2.2).
6. **PARTIAL** is defined, and the callback example fixed (section 2.3).
7. **Errors and storage.** `PRODUCT_DOWNLOAD_FAILED` and `PRODUCT_HASH_MISMATCH` are separate
   (section 2.4), and output keys include the attempt (section 2.2).
8. **QA.** Automated thresholds are disabled, and every output gets manual review (section 2.2).
9. **Input roles** are declared per route / version. The Front-based route is unchanged, and the
   pose-based route is experimental (section 2.8).

### 3.2 Still open

**With Aryan:**
1. **Workflow JSON and mapping: documented in section 2.10 (package r02).** We still need:
   - backend asset IDs for the three inputs (currently null);
   - Aryan's confirmation that the API JSON is the file the worker runs;
   - output size confirmation at 4:5 (README says AS_PRODUCED, examples 832x1888, not validated);
   - the route names per product type;
   - who owns and versions the graph. Proposal: the worker side.
2. **Staging and deployment.** There's no staging worker endpoint yet. Open:
   - deployment ownership: who runs the ComfyUI wrapper and where (GPU host or RunPod);
   - its URL and the auth it supports;
   - the staging environment (with Indra).
3. **Result and QA format.** Automated QA scores aren't validated yet. Open:
   - what the worker returns per output;
   - where QA runs;
   - which identity metric;
   - when a score may gate an output.

   Until then: manual review of every output.
4. **Reference image specs.**
   - Size and format limits per image.
   - The `face_golden_crop` crop spec.
   - The two canonical asset ids for the #60 seed (section 2.7).
   - The product image requirements (mask, flat-lay vs on-model).
5. **Adapter use.**
   - Which tested conditions benefit from 0.4, and the watch items at 0.6.
   - Whether the adapter is loaded from the worker's store by id + sha256, or downloaded.
   - Which ComfyUI inputs "strength" sets.
6. **Pose control.** It is unsupported on the Front-based route (resolved). Still open, for a
   later route: a validated pose workflow, the control type, and how a chosen pose combines with
   Image 1 as the pose /
   framing reference.
7. **Appearance descriptors.** Prompt text, tags, or a reference image per style.
8. **Output.**
   - A validated resolution per route / version (until then, as produced).
   - Whether the graph can honour an aspect ratio without resizing.
   - Whether seeds are reproducible.
   - PNG vs WebP.
9. **Runtime limits.**
   - Time per image, typical and worst case.
   - The job deadline.
   - Concurrency per GPU.
   - Progress reporting.
10. **Errors and retries.** The error codes and `retryable` flags (2.4), and whether OOMs are
    retried internally.
11. **Retention.** How long the worker keeps inputs and outputs.
12. **The experimental pose-based route** (section 2.8): who approves a `pose_base` image, where it
    is registered, and its validation criteria.

**With others:**
- **Indra:**
  - the Railway worker command and queues (1.4 item 4; #63 fixes the routing);
  - the staging environment.
- **Shahida:**
  - charging for PARTIAL: only for delivered outputs (2.3);
  - with Indra: what dispatch does when a customer picks a pose on a route without pose control
    (2.9), and what it does with a customer's aspect ratio while output size is as produced (2.2);
  - the fallback retry policy;
  - the #60 role change (2.7), together with Aryan.

## 4. What changes on our side once agreed (not in this PR)

1. **#60 roles.** Apply the role change in 2.7 once Aryan and Shahida agree (before #60 merges, or
   as a follow-up).
2. **AC-5 (runtime resolver strategy).** Build the payload in 2.2 from the plan. Replace `_comfyui`
   / the base workflow with a worker client: submit, then return. Also:
   - declare input roles per route / version (2.8);
   - send `pose: null` and no pixel size on the Front-based route (2.2, 2.9);
   - apply the pose decision in dispatch once it is made (2.9);
   - use attempt-numbered output keys (2.2).
3. **The rest of the worker path:**
   - add the callback route with signature checks and the reconciliation beat task;
   - route `process_production_job` to a queue the worker consumes (#63);
   - make mock mode fatal when production dispatch is enabled in production.
4. **Customer output URLs.** Return URLs a browser can load: presigned GET or CDN, not `s3://`.
5. **New settings, named only:** `AI_WORKER_URL`, `AI_WORKER_TOKEN`, `AI_WORKER_CALLBACK_SECRET`,
   the input/output URL TTLs, and the job timeout. They're checked at startup like the FASHN
   settings.

All of it stays behind `COMFYUI_MOCK_MODE` / a mock worker in tests, and is never run against
production before a staging E2E (AC-10).
