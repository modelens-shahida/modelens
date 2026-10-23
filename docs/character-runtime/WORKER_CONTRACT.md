# AI worker input contract (proposal)

Status: **proposal for Aryan to review** (2026-10-23). Docs only: no code, migrations or settings
change with this document, and it contains no secrets. Every point still to be agreed is marked
**[to confirm with Aryan]**.

This is blocker 1 in `APPEARANCE_STATUS.md` section 6, "current generations are not
identity-locked". It is the input contract AC-5 (strategy in the resolver) needs before it can
start. File references are to `backend/` on `main`.

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

- **Transport: HTTPS JSON**, contract version `2026-11.v1`. **[to confirm with Aryan]** The worker
  might instead be:
  - ComfyUI with our own wrapper;
  - a RunPod serverless endpoint (`/run` + `/status`);
  - a custom service;
  - or a Celery consumer on a dedicated queue.

  The payload below fits any of them; only the envelope changes.
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
Canonical asset ids, the workflow route name, the descriptors and the pixel sizes are illustrative.
No workflow route is seeded today.

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
    "workflow": { "route": "GARMENT_V1", "version": "1" }
  },

  "references": {
    "reference_set_id": "EE-F-002_V1.0_REF_V1",
    "content_hash": "<sha256 of the ordered (asset_id, sha256) pairs>",
    "images": [
      { "role": "face_front", "asset_id": "EE-F-002_V1.0_CAN_001", "url": "<presigned GET>",
        "sha256": "<64 hex>", "mime": "image/png", "width": 2048, "height": 2048 },
      { "role": "face_34", "asset_id": "EE-F-002_V1.0_CAN_002", "url": "<presigned GET>", "sha256": "<64 hex>",
        "mime": "image/png", "width": 2048, "height": 2048 },
      { "role": "profile", "asset_id": "EE-F-002_V1.0_CAN_003", "url": "<presigned GET>", "sha256": "<64 hex>",
        "mime": "image/png", "width": 2048, "height": 2048 },
      { "role": "body_full", "asset_id": "EE-F-002_V1.0_CAN_010", "url": "<presigned GET>", "sha256": "<64 hex>",
        "mime": "image/png", "width": 1536, "height": 2048 },
      { "role": "body_34", "asset_id": "EE-F-002_V1.0_CAN_011", "url": "<presigned GET>", "sha256": "<64 hex>",
        "mime": "image/png", "width": 1536, "height": 2048 }
    ]
  },

  "adapter": null,

  "product": {
    "product_type": "garment",
    "image": { "url": "<presigned GET>", "sha256": "<64 hex>", "mime": "image/jpeg" },
    "required_reference_roles": ["body_full"]
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

  "pose": {
    "pose_id": "standing", "category": "static", "framing": "full_body",
    "control_image": { "url": "<presigned GET>", "sha256": "<64 hex>", "kind": "openpose" },
    "geometry": { "...": "pose_geometry_presets data, as resolved today" },
    "params": { "...": "pose workflow_params, as resolved today" }
  },

  "camera": { "shot": "full_body", "focal_length_mm": 85, "aspect_ratio": "4:5", "height": "eye", "angle": "front" },

  "scene": {
    "env_id": "ENV-STU-0001", "family": "STUDIO",
    "descriptor": "white seamless studio, clean floor bounce",
    "lighting": { "preset_id": "STUDIO_SOFT_DIFFUSE", "params": { "...": "lighting workflow_params" } }
  },

  "output": {
    "count": 4, "width": 1600, "height": 2000, "format": "png",
    "seed": 123456789, "seed_policy": "increment_per_output",
    "uploads": [
      { "index": 0, "url": "<presigned PUT>", "key": "productions/prd_7f3a…/0.png" },
      { "index": 1, "url": "<presigned PUT>", "key": "productions/prd_7f3a…/1.png" },
      { "index": 2, "url": "<presigned PUT>", "key": "productions/prd_7f3a…/2.png" },
      { "index": 3, "url": "<presigned PUT>", "key": "productions/prd_7f3a…/3.png" }
    ]
  },

  "qa": {
    "profile_ids": ["QA-PROFILE-CATALOG-001", "QA-PROFILE-APPEARANCE-HAIR-001"],
    "identity_hard_gate": 94.0,
    "scored_by": "api",
    "fallback_retry": { "enabled": false }
  },

  "callback": { "url": "https://api.modelens.ai/api/v1/internal/worker/jobs/prd_7f3a…/result",
                "signature": "hmac-sha256" }
}
```

With `REFERENCE_PLUS_ADAPTER`, `adapter` is set:

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

Field rules:

| Field | Source (after AC-1…AC-5) | Rules | Open |
|---|---|---|---|
| `job_id` | `productions.production_id` | the worker's idempotency key, together with `attempt` | |
| `attempt` | starts at 1 | a new attempt only from an admin re-run or the retry policy, never from transport retries | |
| `deadline_at` | submit time + job timeout (setting) | the worker stops and reports `TIMEOUT` after it | value **[to confirm with Aryan]** |
| `character.*` | current LOCKED `character_registry_versions` row | informational for the worker; identity comes from `references` | |
| `runtime.strategy` | resolver step 8 | `REFERENCE_ONLY` or `REFERENCE_PLUS_ADAPTER` | |
| `runtime.workflow` | the capability pack's `workflow_route` / `workflow_version` | the worker maps the route to its own graph; **we stop sending a graph** | route names **[to confirm with Aryan]** |
| `references.images[]` | the PRODUCTION reference set (#60): role, `asset_id`, `content_hash_sha256` | the worker must check each file's sha256 before use, and fail with `REFERENCE_HASH_MISMATCH` otherwise; roles as in #60 | how many references and which roles each workflow uses, size limits, whether face crops are wanted **[to confirm with Aryan]** |
| `adapter` | runtime profile / promoted capability snapshot; `PRODUCTION` only | `null` for `REFERENCE_ONLY`; strengths come only from data (never a worker default) | whether the worker loads adapters from its own store by id + sha256 or downloads them via presigned URL; how "strength" maps to the worker's LoRA / IP-Adapter weights; whether one number or per-block weights **[to confirm with Aryan]** |
| `product.image` | the brand asset of the dispatch (`productions.product_asset_id`) | presigned GET | whether the worker needs a mask or a flat-lay vs on-model image; max size **[to confirm with Aryan]** |
| `appearance.*.descriptor` | new admin-only field on `appearance_options` (planned with AC-2) | **internal descriptors, never customer labels**; `grooming` stays `null` until defined | descriptor format (prompt text, structured tags, or a reference image per style) **[to confirm with Aryan]** |
| `pose.control_image` | `pose_definitions.control_reference` | presigned GET; `null` if the pose has none | control type (OpenPose, depth, canny) **[to confirm with Aryan]** |
| `camera` | `focal_length_mm` / `aspect_ratio` today; shot/height/angle once camera options exist | | how the worker applies focal length **[to confirm with Aryan]** |
| `scene` | the location and lighting presets' `technical_config` | `descriptor` is internal text, not the customer label | |
| `output.width/height` | aspect ratio × resolution (`app/services/production_presets.py`) | exact pixels, so the worker never guesses | max resolution per workflow **[to confirm with Aryan]** |
| `output.seed` | `params.seed` (already generated) | output *i* uses `seed + i` | whether seeds are reproducible on the worker **[to confirm with Aryan]** |
| `output.uploads[]` | presigned PUT per output to `productions/<production_id>/<index>.png` | deterministic keys make a duplicate upload overwrite rather than add | PUT TTL **[to confirm with Aryan]** |
| `qa` | runtime profile + capability QA profiles | `scored_by: api` = the worker only generates; the API scores after the callback. `fallback_retry.enabled` mirrors `runtime_profiles.fallback_retry_enabled` (default false, Shahida's decision) | whether QA runs on the worker (it has the GPU) or in the API **[to confirm with Aryan]** |

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
  "status": "COMPLETED",
  "outputs": [
    { "index": 0, "key": "productions/prd_7f3a…/0.png", "sha256": "<64 hex>", "width": 1600, "height": 2000,
      "mime": "image/png", "seed": 123456789, "strength_used": null },
    { "index": 1, "key": "productions/prd_7f3a…/1.png", "sha256": "<64 hex>", "width": 1600, "height": 2000,
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

- **`status`:**
  - `COMPLETED`: every output is uploaded.
  - `PARTIAL`: some outputs are uploaded, the rest are in `failed_outputs`.
  - `FAILED`: nothing usable was produced; the body has one `error`.
  - `CANCELLED`.
- **What the API does with a callback:**
  1. It checks the signature, `job_id` and `attempt`.
  2. For each output, it reads the object at `key` and compares its sha256 to the reported one.
     A mismatch makes that output failed (`OUTPUT_HASH_MISMATCH`).
  3. It registers each good output as a brand asset, recording the sha256 in `assets.meta`.
  4. It runs QA.
  5. It finalizes credits for the delivered outputs and refunds the rest once. This uses the
     existing ledger and `lock_reservation`, so a duplicate callback is a no-op.
- **Partial-credit rule.** Charging only for delivered outputs **[to confirm with Shahida]**.
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
| `PRODUCT_FETCH_FAILED` | product image couldn't be fetched | true | re-sign and resubmit once |
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
  - A retryable error (`REFERENCE_FETCH_FAILED`, `PRODUCT_FETCH_FAILED`, `UPLOAD_FAILED`) gets one
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
  - **Worker → storage:** the deterministic output `key`.
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

## 3. To confirm with Aryan (summary)

1. **What the worker is.** ComfyUI behind our wrapper, RunPod serverless, a custom service, or a
   Celery consumer? Its staging URL, and the auth it supports.
2. **References.** How many images and which roles each workflow takes, and in what form (full
   images, face crops, embeddings precomputed on the worker?). Plus size and format limits.
3. **Adapter.** Is it loaded from the worker's store by id + sha256, or downloaded? What does
   "strength" map to (LoRA weight, IP-Adapter weight, both), as one number or several?
4. **Workflows.** Route names per product type, and who owns the graph. The graph should live on
   the worker side, versioned, and stop being sent by the API.
5. **Appearance descriptors.** Prompt text, tags, or a reference image per style?
6. **Pose control.** Which control type, and does each pose need its own control image?
7. **Output.** Maximum resolution per workflow, whether seeds are reproducible, and the format
   (PNG vs WebP).
8. **QA.** Does it run on the worker or in the API, and with which identity metric?
9. **Limits.** Typical and worst-case time per image, the job deadline, concurrency per GPU, and
   whether the worker can report progress.
10. **Errors and retries.** The error code list and `retryable` flags, and whether OOMs are retried
    internally.
11. **Retention.** How long the worker keeps inputs and outputs.

Also to confirm:
- **Indra:** the Railway worker command and queues (1.4 item 4), and the staging environment.
- **Shahida:** charging only for delivered outputs (2.3), and the fallback retry policy.

## 4. What changes on our side once agreed (not in this PR)

1. **AC-5 (runtime resolver strategy).** Build the payload in 2.2 from the plan. Replace `_comfyui`
   / the base workflow with a worker client: submit, then return.
2. **The rest of the worker path:**
   - add the callback route with signature checks and the reconciliation beat task;
   - route `process_production_job` to a queue the worker consumes;
   - make mock mode fatal when production dispatch is enabled in production.
3. **Customer output URLs.** Return URLs a browser can load: presigned GET or CDN, not `s3://`.
4. **New settings, named only:** `AI_WORKER_URL`, `AI_WORKER_TOKEN`, `AI_WORKER_CALLBACK_SECRET`,
   the input/output URL TTLs, and the job timeout. They're checked at startup like the FASHN
   settings.

All of it stays behind `COMFYUI_MOCK_MODE` / a mock worker in tests, and is never run against
production before a staging E2E (AC-10).
