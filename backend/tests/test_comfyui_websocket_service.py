import pytest
import asyncio
from app.services.comfyui_service import ComfyUIService


SAMPLE_ROSANNE_API_WORKFLOW = {
    "14": {
        "inputs": {"text": "Original default scene"},
        "class_type": "PrimitiveNode",
        "_meta": {"title": "Scene Description Text"}
    },
    "22": {
        "inputs": {"image": "default_pose.png"},
        "class_type": "LoadImage",
        "_meta": {"title": "DWPose Reference Loader"}
    },
    "30": {
        "inputs": {"lora_name": "rosanne_v1.safetensors"},
        "class_type": "LoraLoader"
    }
}


def test_inject_node_input_scene_text():
    service = ComfyUIService(mock_mode=True)
    updated_wf = service.inject_node_input(
        workflow=SAMPLE_ROSANNE_API_WORKFLOW,
        node_id="14",
        field_name="text",
        value="Seated at a luxury marble restaurant table, wearing silk dress"
    )

    assert updated_wf["14"]["inputs"]["text"] == "Seated at a luxury marble restaurant table, wearing silk dress"
    # Original template remains unchanged
    assert SAMPLE_ROSANNE_API_WORKFLOW["14"]["inputs"]["text"] == "Original default scene"


def test_inject_node_input_pose_image():
    service = ComfyUIService(mock_mode=True)
    updated_wf = service.inject_node_input(
        workflow=SAMPLE_ROSANNE_API_WORKFLOW,
        node_id=22,
        field_name="image",
        value="editorial_pose_04.png"
    )

    assert updated_wf["22"]["inputs"]["image"] == "editorial_pose_04.png"


def test_inject_node_input_nonexistent_node():
    service = ComfyUIService(mock_mode=True)
    updated_wf = service.inject_node_input(
        workflow=SAMPLE_ROSANNE_API_WORKFLOW,
        node_id="999",
        field_name="text",
        value="Test"
    )

    assert "999" not in updated_wf


@pytest.mark.asyncio
async def test_websocket_listener_mock_mode():
    service = ComfyUIService(mock_mode=True)
    prompt_id = await service.submit_workflow(SAMPLE_ROSANNE_API_WORKFLOW, client_id="test_client_123")
    assert prompt_id.startswith("mock_prompt_")

    result = await service.listen_websocket_completion(prompt_id=prompt_id, client_id="test_client_123")
    assert result["status"] == "completed"
    assert len(result["outputs"]) > 0
