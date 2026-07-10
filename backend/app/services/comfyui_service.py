import json
import uuid
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx

logger = logging.getLogger("modelens.comfyui")

COMFYUI_TIMEOUT = 30
COMFYUI_POLL_INTERVAL = 2
COMFYUI_MAX_POLLS = 150  # 5 minutes


class ComfyUIService:
    """
    Provider-independent ComfyUI generation service.
    Supports mock mode for local development.
    """

    def __init__(self, base_url: str = "http://localhost:8188", mock_mode: bool = True):
        self.base_url = base_url.rstrip("/")
        self.mock_mode = mock_mode

    def _build_workflow(
        self,
        workflow_template: dict,
        character_lora: Optional[str] = None,
        prompt: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        garment_image: Optional[str] = None,
        pose_image: Optional[str] = None,
        location_image: Optional[str] = None,
        seed: Optional[int] = None,
        width: int = 1024,
        height: int = 1024,
        generation_params: Optional[dict] = None,
    ) -> dict:
        """
        Build a ComfyUI workflow JSON by dynamically replacing placeholders.
        """
        workflow = json.loads(json.dumps(workflow_template))  # Deep copy

        for node_id, node in workflow.items():
            inputs = node.get("inputs", {})
            class_type = node.get("class_type", "")

            # Replace LoRA model
            if class_type == "LoraLoader" and character_lora:
                inputs["lora_name"] = character_lora

            # Replace prompt
            if class_type == "CLIPTextEncode":
                if "positive" in str(node_id).lower() and prompt:
                    inputs["text"] = prompt
                elif "negative" in str(node_id).lower() and negative_prompt:
                    inputs["text"] = negative_prompt

            # Replace seed
            if "seed" in inputs and seed is not None:
                inputs["seed"] = seed

            # Replace dimensions
            if "width" in inputs:
                inputs["width"] = width
            if "height" in inputs:
                inputs["height"] = height

            # Replace image inputs
            if class_type == "LoadImage":
                node_title = node.get("_meta", {}).get("title", "")
                if "garment" in node_title.lower() and garment_image:
                    inputs["image"] = garment_image
                elif "pose" in node_title.lower() and pose_image:
                    inputs["image"] = pose_image
                elif "location" in node_title.lower() and location_image:
                    inputs["image"] = location_image

        return workflow

    async def submit_workflow(self, workflow: dict, client_id: str = None) -> str:
        """Submit a workflow to ComfyUI and return the prompt_id."""
        if self.mock_mode:
            mock_id = f"mock_prompt_{uuid.uuid4().hex[:8]}"
            logger.info(f"[ComfyUI Mock] Submitted workflow, prompt_id: {mock_id}")
            return mock_id

        client_id = client_id or str(uuid.uuid4())
        async with httpx.AsyncClient(timeout=COMFYUI_TIMEOUT) as client:
            response = await client.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow, "client_id": client_id},
            )
            response.raise_for_status()
            data = response.json()
            return data["prompt_id"]

    async def poll_until_complete(self, prompt_id: str) -> Dict[str, Any]:
        """Poll ComfyUI until generation is complete."""
        if self.mock_mode:
            await asyncio.sleep(1)
            return {
                "status": "completed",
                "outputs": [
                    {"filename": f"mock_output_{uuid.uuid4().hex[:8]}.png", "type": "output"}
                ],
            }

        for _ in range(COMFYUI_MAX_POLLS):
            async with httpx.AsyncClient(timeout=COMFYUI_TIMEOUT) as client:
                response = await client.get(f"{self.base_url}/history/{prompt_id}")
                if response.status_code == 200:
                    history = response.json()
                    if prompt_id in history:
                        outputs = []
                        for node_output in history[prompt_id].get("outputs", {}).values():
                            for img in node_output.get("images", []):
                                outputs.append(img)
                        return {"status": "completed", "outputs": outputs}

            await asyncio.sleep(COMFYUI_POLL_INTERVAL)

        raise TimeoutError(f"ComfyUI generation timed out for prompt_id: {prompt_id}")

    async def download_output(self, filename: str) -> bytes:
        """Download generated output from ComfyUI."""
        if self.mock_mode:
            # Return minimal valid PNG bytes
            import base64
            mock_png = base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            )
            return mock_png

        async with httpx.AsyncClient(timeout=COMFYUI_TIMEOUT) as client:
            response = await client.get(
                f"{self.base_url}/view",
                params={"filename": filename, "type": "output"},
            )
            response.raise_for_status()
            return response.content


def get_comfyui_service() -> ComfyUIService:
    """Get configured ComfyUI service instance."""
    from app.config import settings
    base_url = getattr(settings, "COMFYUI_URL", "http://localhost:8188")
    mock_mode = getattr(settings, "COMFYUI_MOCK_MODE", True)
    return ComfyUIService(base_url=base_url, mock_mode=mock_mode)
