"""
Generation Pipeline Orchestrator
Handles job lifecycle: queuing, status tracking, timeout, retries, cancellation.
Integrates ComfyUIService with dynamic inputs and WebSocket progress updates.
"""
import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.comfyui_service import get_comfyui_service, ComfyUIService

# ========================== Constants ============================

JOB_TIMEOUT_SECONDS = 600       # 10 minutes max per job
RETRY_DELAYS = [30, 60, 120]    # Exponential backoff in seconds
MAX_RETRIES = 3
PROGRESS_POLL_INTERVAL = 2      # Seconds between status polls

# ========================== Pipeline Stages ======================

PIPELINE_STAGES = {
    "queued":           0,
    "preprocessing":    15,
    "generating":       40,
    "postprocessing":   75,
    "quality_check":    90,
    "completed":        100,
    "failed":           0,
    "cancelled":        0,
    "timeout":          0,
}


# ========================== Input Builder ========================

class GenerationInputBuilder:
    """Build dynamic ComfyUI workflow inputs without modifying core workflow."""

    def __init__(self, service: ComfyUIService):
        self.service = service

    def build(
        self,
        base_workflow: dict,
        scene_description: Optional[str] = None,
        pose_filename: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        resolution: str = "2K",
        aspect_ratio: str = "4:5",
        extra_inputs: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Inject dynamic inputs into workflow nodes."""
        workflow = dict(base_workflow)

        # Node 14: Scene/text prompt
        if scene_description:
            workflow = self.service.inject_node_input(workflow, "14", "text", scene_description)

        # Node 22: Pose reference image
        if pose_filename:
            workflow = self.service.inject_node_input(workflow, "22", "image", pose_filename)

        # Node 7: Negative prompt
        if negative_prompt:
            workflow = self.service.inject_node_input(workflow, "7", "text", negative_prompt)

        # Additional dynamic inputs
        if extra_inputs:
            for node_id, fields in extra_inputs.items():
                for field_name, value in fields.items():
                    workflow = self.service.inject_node_input(workflow, node_id, field_name, value)

        return workflow


# ========================== Job Lifecycle Manager ================

class GenerationJobManager:
    """Manages generation job lifecycle with retries, timeouts, and cancellation."""

    def __init__(self, db: AsyncSession, redis_client=None):
        self.db = db
        self.redis = redis_client
        self.service = get_comfyui_service()
        self.input_builder = GenerationInputBuilder(self.service)

    async def update_job_status(
        self,
        job,
        status: str,
        progress: int = None,
        error_message: str = None,
    ):
        """Update job status and publish WebSocket progress event."""
        job.status = status
        if progress is not None:
            job.progress = progress
        if error_message:
            job.error_message = error_message[:500]
        job.updated_at = datetime.utcnow()

        await self.db.commit()

        # Publish WebSocket event
        if self.redis:
            import json
            event = {
                "type": "job.progress",
                "job_id": job.id,
                "status": status,
                "progress": progress or PIPELINE_STAGES.get(status, 0),
                "timestamp": datetime.utcnow().isoformat(),
            }
            try:
                await self.redis.publish(
                    f"brand:{job.brand_id}:events",
                    json.dumps(event)
                )
            except Exception as e:
                print(f"[Pipeline] WebSocket publish failed: {e}")

    async def run_with_timeout(
        self,
        job,
        workflow_inputs: Dict[str, Any],
        timeout: float = JOB_TIMEOUT_SECONDS,
    ) -> Dict[str, Any]:
        """Run generation with timeout protection."""
        try:
            return await asyncio.wait_for(
                self._run_generation(job, workflow_inputs),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            await self.update_job_status(
                job, "failed",
                error_message=f"Generation timed out after {timeout}s"
            )
            raise

    async def _run_generation(self, job, workflow_inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Core generation execution pipeline."""
        client_id = str(uuid.uuid4())

        # Stage 1: Preprocessing
        await self.update_job_status(job, "preprocessing", PIPELINE_STAGES["preprocessing"])

        # Build dynamic workflow
        base_workflow = self._get_base_workflow()
        workflow = self.input_builder.build(
            base_workflow,
            scene_description=workflow_inputs.get("scene_description"),
            pose_filename=workflow_inputs.get("pose_filename"),
            negative_prompt=workflow_inputs.get("negative_prompt"),
            resolution=workflow_inputs.get("resolution", "2K"),
            aspect_ratio=workflow_inputs.get("aspect_ratio", "4:5"),
            extra_inputs=workflow_inputs.get("extra_inputs"),
        )

        # Stage 2: Submit to ComfyUI
        await self.update_job_status(job, "generating", PIPELINE_STAGES["generating"])

        prompt_id = await self.service.submit_workflow(workflow, client_id=client_id)
        print(f"[Pipeline] Job {job.id} submitted to ComfyUI: {prompt_id}")

        # Stage 3: Track via WebSocket
        await self.service.listen_websocket_completion(prompt_id, client_id=client_id)

        # Stage 4: Get outputs
        result = await self.service.poll_until_complete(prompt_id)
        outputs = result.get("outputs", [])

        # Stage 5: Download output
        await self.update_job_status(job, "postprocessing", PIPELINE_STAGES["postprocessing"])

        image_bytes = None
        if outputs:
            filename = outputs[0].get("filename", "output.png")
            image_bytes = await self.service.download_output(filename)
        else:
            image_bytes = await self.service.download_output("output.png")

        return {
            "prompt_id": prompt_id,
            "image_bytes": image_bytes,
            "outputs": outputs,
        }

    def _get_base_workflow(self) -> dict:
        """Return base ComfyUI workflow template."""
        return {
            "14": {
                "class_type": "CLIPTextEncode",
                "_meta": {"title": "positive prompt"},
                "inputs": {"text": "", "clip": ["4", 1]},
            },
            "7": {
                "class_type": "CLIPTextEncode",
                "_meta": {"title": "negative prompt"},
                "inputs": {"text": "blurry, low quality", "clip": ["4", 1]},
            },
            "22": {
                "class_type": "LoadImage",
                "_meta": {"title": "pose reference"},
                "inputs": {"image": "pose_reference.png", "upload": "image"},
            },
        }

    async def cancel_job(self, job) -> bool:
        """Cancel an active generation job."""
        if job.status in ("completed", "failed", "cancelled"):
            return False
        await self.update_job_status(job, "cancelled", 0)
        print(f"[Pipeline] Job {job.id} cancelled.")
        return True

    async def register_output_asset(
        self,
        db: AsyncSession,
        job,
        image_bytes: bytes,
        storage_service,
        metadata: Optional[Dict] = None,
    ):
        """Save output image and register as Asset linked to job."""
        from app.models.db import Asset

        filename = f"generation_{job.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.png"
        storage_path = storage_service.save_file_bytes(filename, image_bytes)

        asset = Asset(
            brand_id=job.brand_id,
            name=f"Generated - Job {job.id}",
            filename=filename,
            storage_path=storage_path,
            asset_type="generated",
            status="active",
            meta={
                "source": "generation_pipeline",
                "job_id": job.id,
                "job_type": getattr(job, "job_type", "generation"),
                **(metadata or {}),
            }
        )
        db.add(asset)
        await db.flush()

        job.asset_id = asset.id
        await db.commit()

        return asset


# ========================== Retry Manager ========================

async def run_with_retries(
    job_manager: GenerationJobManager,
    job,
    workflow_inputs: Dict[str, Any],
    max_retries: int = MAX_RETRIES,
) -> Dict[str, Any]:
    """Execute generation with automatic retry on failure."""
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                delay = RETRY_DELAYS[min(attempt - 1, len(RETRY_DELAYS) - 1)]
                print(f"[Pipeline] Job {job.id} retry {attempt}/{max_retries} after {delay}s")
                await asyncio.sleep(delay)
                await job_manager.update_job_status(job, "queued", 0)

            result = await job_manager.run_with_timeout(job, workflow_inputs)
            return result

        except asyncio.TimeoutError as e:
            last_error = e
            print(f"[Pipeline] Job {job.id} attempt {attempt} timed out")
            if attempt == max_retries:
                break

        except Exception as e:
            last_error = e
            print(f"[Pipeline] Job {job.id} attempt {attempt} failed: {e}")
            if attempt == max_retries:
                break

    # All retries exhausted
    await job_manager.update_job_status(
        job, "failed", 0,
        error_message=f"Failed after {max_retries + 1} attempts: {str(last_error)[:200]}"
    )
    raise last_error
