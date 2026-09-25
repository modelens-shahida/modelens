# Generation Pipeline API Contract

## Architecture
Frontend -> FastAPI -> Celery Worker -> GenerationJobManager -> ComfyUI/FASHN -> Asset Registry

## Job Lifecycle
queued (0%) -> preprocessing (15%) -> generating (40%) -> postprocessing (75%) -> quality_check (90%) -> completed (100%)

## Environment Variables
- COMFYUI_HOST: localhost
- COMFYUI_MOCK_MODE: true
- FASHN_API_KEY: mock
- GEMINI_API_KEY: mock
- INTERNAL_CALLBACK_SECRET: modelens-internal-secret
- TEMPLATES_BACKEND_URL: http://localhost:4000

## Retry Policy
- Max retries: 3
- Delays: 30s, 60s, 120s
- Timeout: 600s per attempt

## Node Mapping
- Node 14: Scene prompt
- Node 7: Negative prompt
- Node 22: Pose reference image
