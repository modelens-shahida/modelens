import pytest
from unittest.mock import patch, MagicMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import VideoProject, VideoClip, VideoRender, User
from app.worker import _process_video_generation_async, _process_video_render_async

@pytest.mark.asyncio
async def test_create_video_project(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    brand_id = test_data["brand"].id

    res = await client.post("/api/v1/video-projects", json={
        "brand_id": brand_id,
        "name": "Summer Collection Runway",
        "master_prompt": "Elegant fashion walk",
        "aspect_ratio": "16:9",
        "mode": "standard",
    }, headers=editor_headers)

    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert "project_id" in data
    assert data["name"] == "Summer Collection Runway"
    assert data["status"] == "draft"

    # Verify db record
    db_session.expire_all()
    project_result = await db_session.execute(select(VideoProject).where(VideoProject.id == data["project_id"]))
    project = project_result.scalars().first()
    assert project is not None
    assert project.name == "Summer Collection Runway"


@pytest.mark.asyncio
async def test_get_video_project_not_found(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get("/api/v1/video-projects/9999", headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_create_storyboard(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id
    editor_id = editor_user.id

    project = VideoProject(
        user_id=editor_id,
        brand_id=brand_id,
        name="Winter Coats Video",
        status="draft"
    )
    db_session.add(project)
    await db_session.commit()
    project_id = project.id

    # Create storyboard of 3 clips
    res = await client.post(f"/api/v1/video-projects/{project_id}/storyboard", json={
        "master_prompt": "Models posing in snowy studio",
        "motion_preset": "PAN",
        "duration": 5.0,
        "num_clips": 3,
        "start_image_url": "/uploads/start.png",
        "end_image_url": "/uploads/end.png",
    }, headers=editor_headers)

    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["clips_created"] == 3
    assert data["motion_preset"] == "PAN"

    # Check database records
    db_session.expire_all()
    clips_result = await db_session.execute(
        select(VideoClip).where(VideoClip.project_id == project_id).order_by(VideoClip.position)
    )
    clips = clips_result.scalars().all()
    assert len(clips) == 3
    assert clips[0].position == 0
    assert clips[0].start_image_url == "/uploads/start.png"
    assert clips[2].position == 2
    assert clips[2].end_image_url == "/uploads/end.png"


@pytest.mark.asyncio
async def test_generate_video_insufficient_credits(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id
    editor_id = editor_user.id

    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    user.credits = 10  # Needs 15 for 3 clips
    await db_session.commit()

    project = VideoProject(
        user_id=editor_id,
        brand_id=brand_id,
        name="Low Credits Project",
        status="draft"
    )
    db_session.add(project)
    await db_session.commit()

    # Add 3 clips
    for i in range(3):
        clip = VideoClip(project_id=project.id, position=i, status="queued")
        db_session.add(clip)
    await db_session.commit()

    res = await client.post(f"/api/v1/video-projects/{project.id}/generate", json={"provider": "AUTO"}, headers=editor_headers)
    assert res.status_code == status.HTTP_402_PAYMENT_REQUIRED
    assert "Insufficient credits" in res.json()["detail"]


@pytest.mark.asyncio
async def test_generate_video_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id
    editor_id = editor_user.id

    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    user.credits = 100
    await db_session.commit()
    starting_credits = user.credits

    project = VideoProject(
        user_id=editor_id,
        brand_id=brand_id,
        name="Promo Video",
        status="draft"
    )
    db_session.add(project)
    await db_session.commit()

    # Add 2 clips (costs 10 credits)
    for i in range(2):
        clip = VideoClip(project_id=project.id, position=i, status="queued")
        db_session.add(clip)
    await db_session.commit()

    with patch("app.routers.video_projects.process_video_generation.delay") as mock_celery:
        res = await client.post(f"/api/v1/video-projects/{project.id}/generate", json={"provider": "AUTO"}, headers=editor_headers)
        assert res.status_code == status.HTTP_202_ACCEPTED
        data = res.json()
        assert data["status"] == "generating"
        assert data["clips_queued"] == 2
        assert data["credits_reserved"] == 10

        mock_celery.assert_called_once_with(project.id, "AUTO")

        # Verify credits deducted
        db_session.expire_all()
        user_result = await db_session.execute(select(User).where(User.id == editor_id))
        user = user_result.scalars().first()
        assert user.credits == starting_credits - 10


@pytest.mark.asyncio
async def test_render_video_project(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id
    editor_id = editor_user.id

    project = VideoProject(
        user_id=editor_id,
        brand_id=brand_id,
        name="Render Project",
        status="ready_to_render"
    )
    db_session.add(project)
    await db_session.commit()

    with patch("app.routers.video_projects.process_video_render.delay") as mock_celery:
        res = await client.post(f"/api/v1/video-projects/{project.id}/render", json={
            "audio_url": "https://cdn.example.com/music.mp3",
            "logo_url": "https://cdn.example.com/logo.png",
            "resolution": "1080p"
        }, headers=editor_headers)

        assert res.status_code == status.HTTP_202_ACCEPTED
        data = res.json()
        assert "render_id" in data
        assert data["status"] == "queued"

        mock_celery.assert_called_once_with(data["render_id"])


@pytest.mark.asyncio
async def test_get_generation_job_status(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    brand_id = test_data["brand"].id
    editor_id = editor_user.id

    project = VideoProject(
        user_id=editor_id,
        brand_id=brand_id,
        name="Status Project",
        status="generating"
    )
    db_session.add(project)
    await db_session.commit()

    clip = VideoClip(
        project_id=project.id,
        position=0,
        status="completed",
        clip_url="https://cdn.example.com/clip1.mp4",
        provider="RUNWAY"
    )
    db_session.add(clip)
    await db_session.commit()

    res = await client.get(f"/api/v1/generation-jobs/{clip.id}", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["status"] == "completed"
    assert data["clip_url"] == "https://cdn.example.com/clip1.mp4"
    assert data["provider"] == "RUNWAY"


class MockSessionContext:
    def __init__(self, session):
        self.session = session
    async def __aenter__(self):
        return self.session
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


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
