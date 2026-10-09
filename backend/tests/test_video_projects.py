"""Video project worker tasks (generation and render).

The /api/v1/video-projects router was replaced by /api/v1/video (presets + jobs,
see test_video_studio.py); its router tests were removed with it.
"""
import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import VideoProject, VideoClip, VideoRender
from app.worker import _process_video_generation_async, _process_video_render_async


class MockSessionContext:
    def __init__(self, session):
        self.session = session
    async def __aenter__(self):
        return self.session
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_process_video_generation_celery_task(db_session: AsyncSession, test_data: dict):
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id
    editor_id = editor_user.id

    project = VideoProject(
        user_id=editor_id,
        brand_id=brand_id,
        name="Promotion",
        status="generating"
    )
    db_session.add(project)
    await db_session.commit()

    clip = VideoClip(
        project_id=project.id,
        position=0,
        status="queued",
        duration=4.0
    )
    db_session.add(clip)
    await db_session.commit()

    mock_task_self = MagicMock()

    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)):
        await _process_video_generation_async(mock_task_self, project.id, "AUTO")

    # Verify clip status is completed and provider is set to MOCK because of no key
    await db_session.refresh(clip)
    assert clip.status == "completed"
    assert clip.provider == "MOCK"
    assert clip.credits_consumed == 5

    await db_session.refresh(project)
    assert project.status == "ready_to_render"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_process_video_render_celery_task(db_session: AsyncSession, test_data: dict):
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id
    editor_id = editor_user.id

    project = VideoProject(
        user_id=editor_id,
        brand_id=brand_id,
        name="Full Video Project",
        status="ready_to_render"
    )
    db_session.add(project)
    await db_session.commit()

    clip = VideoClip(
        project_id=project.id,
        position=0,
        status="completed",
        clip_url="https://cdn.example.com/clip1.mp4",
        duration=4.0
    )
    db_session.add(clip)
    await db_session.commit()

    render = VideoRender(
        project_id=project.id,
        status="queued"
    )
    db_session.add(render)
    await db_session.commit()

    mock_task_self = MagicMock()

    # Mock subprocess.run for FFmpeg concat execution
    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("subprocess.run") as mock_sub:
        
        await _process_video_render_async(mock_task_self, render.id)

    await db_session.refresh(render)
    assert render.status == "completed"
    assert render.duration_seconds == 4.0
