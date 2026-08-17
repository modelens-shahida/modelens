import pytest
import pytest_asyncio
from httpx import AsyncClient
from fastapi import status
from sqlalchemy import select
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import AngleShot, AngleShotCompatibility, AngleShotVersion, User, Campaign, Asset, ShootAngleShot
from app.worker import _process_custom_angle_shot_async


@pytest.mark.asyncio
async def test_list_angle_shots(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    # Seed angle shots
    shot_a = AngleShot(
        name="Classic Adult Full Body",
        code="adult-full-body",
        category="adult",
        framing="FULL_BODY",
        pose="relaxed",
        is_custom=False,
        is_visible=True,
        sort_order=10,
    )
    shot_b = AngleShot(
        name="Kids Upper Body Pockets",
        code="kids-upper-body",
        category="kids",
        framing="UPPER_BODY",
        pose="pockets",
        is_custom=True,
        is_visible=True,
        sort_order=20,
    )
    shot_c = AngleShot(
        name="Archived Preset",
        code="archived-preset",
        category="adult",
        is_visible=False,
    )

    db_session.add_all([shot_a, shot_b, shot_c])
    await db_session.commit()

    # Add compatibility rule for shot_a with T-SHIRT
    compat = AngleShotCompatibility(
        angle_shot_id=shot_a.id,
        product_type="T-SHIRT",
        compatible=True,
    )
    db_session.add(compat)
    await db_session.commit()

    # 1. Test listing all visible shots
    res = await client.get("/api/v1/angle-shots", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    items = res.json()["items"]
    assert len(items) == 2
    assert any(x["name"] == "Classic Adult Full Body" for x in items)
    assert any(x["name"] == "Kids Upper Body Pockets" for x in items)
    assert not any(x["name"] == "Archived Preset" for x in items)

    # 2. Filter by category
    res = await client.get("/api/v1/angle-shots?category=kids", headers=editor_headers)
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["name"] == "Kids Upper Body Pockets"

    # 3. Filter by framing
    res = await client.get("/api/v1/angle-shots?framing=FULL_BODY", headers=editor_headers)
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["name"] == "Classic Adult Full Body"

    # 4. Filter by is_custom
    res = await client.get("/api/v1/angle-shots?is_custom=true", headers=editor_headers)
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["name"] == "Kids Upper Body Pockets"

    # 5. Filter by garment_type
    res = await client.get("/api/v1/angle-shots?garment_type=T-SHIRT", headers=editor_headers)
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["name"] == "Classic Adult Full Body"

    # 6. Filter by search
    res = await client.get("/api/v1/angle-shots?search=pockets", headers=editor_headers)
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["name"] == "Kids Upper Body Pockets"


@pytest.mark.asyncio
async def test_get_angle_shot_details(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    shot = AngleShot(
        name="Test Angle Shot",
        framing="FULL_BODY",
        pose="standing",
        is_visible=True,
    )
    db_session.add(shot)
    await db_session.commit()

    compat = AngleShotCompatibility(
        angle_shot_id=shot.id,
        product_type="JEANS",
        compatible=True,
        warning_message="Avoid loose denim",
    )
    db_session.add(compat)
    await db_session.commit()

    # Get success
    res = await client.get(f"/api/v1/angle-shots/{shot.id}", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["name"] == "Test Angle Shot"
    assert len(data["compatibilities"]) == 1
    assert data["compatibilities"][0]["product_type"] == "JEANS"
    assert data["compatibilities"][0]["warning"] == "Avoid loose denim"

    # Get 404
    res = await client.get("/api/v1/angle-shots/99999", headers=editor_headers)
    assert res.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_create_custom_angle_shot(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    payload = {
        "name": "Custom Runway Pose",
        "code": "runway-pose-1",
        "category": "adult",
        "framing": "FULL_BODY",
        "pose": "walking",
        "compatible_products": ["Dress", "Skirt"],
    }

    res = await client.post("/api/v1/angle-shots", json=payload, headers=editor_headers)
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["name"] == "Custom Runway Pose"
    assert data["status"] == "active"
    assert data["version"] == 1

    # Verify preset in database
    db_shot = await db_session.get(AngleShot, data["id"])
    assert db_shot is not None
    assert db_shot.is_custom is True

    # Verify compatibility list
    compats_res = await db_session.execute(
        select(AngleShotCompatibility).where(AngleShotCompatibility.angle_shot_id == db_shot.id)
    )
    compats = compats_res.scalars().all()
    assert len(compats) == 2
    assert {c.product_type for c in compats} == {"DRESS", "SKIRT"}

    # Verify initial version snapshot
    version_res = await db_session.execute(
        select(AngleShotVersion).where(AngleShotVersion.angle_shot_id == db_shot.id)
    )
    versions = version_res.scalars().all()
    assert len(versions) == 1
    assert versions[0].version == 1
    assert versions[0].configuration["pose"] == "walking"


@pytest.mark.asyncio
async def test_update_angle_shot(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    shot = AngleShot(
        name="Initial Shot Name",
        framing="FULL_BODY",
        pose="standing",
        version=1,
    )
    db_session.add(shot)
    await db_session.commit()

    payload = {
        "name": "Updated Shot Name",
        "pose": "hands-in-pockets",
        "change_note": "Changed pose concept",
    }

    res = await client.patch(f"/api/v1/angle-shots/{shot.id}", json=payload, headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["version"] == 2
    assert res.json()["name"] == "Updated Shot Name"

    # Verify database state
    await db_session.refresh(shot)
    assert shot.pose == "hands-in-pockets"

    # Verify new version created
    v_res = await db_session.execute(
        select(AngleShotVersion)
        .where(AngleShotVersion.angle_shot_id == shot.id)
        .order_by(AngleShotVersion.version.desc())
    )
    latest_version = v_res.scalars().first()
    assert latest_version is not None
    assert latest_version.version == 2
    assert latest_version.change_note == "Changed pose concept"
    assert latest_version.configuration["pose"] == "hands-in-pockets"


@pytest.mark.asyncio
async def test_delete_angle_shot(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    shot = AngleShot(
        name="Shot to delete",
        is_visible=True,
        status="active",
    )
    db_session.add(shot)
    await db_session.commit()

    res = await client.delete(f"/api/v1/angle-shots/{shot.id}", headers=editor_headers)
    assert res.status_code == status.HTTP_204_NO_CONTENT

    # Verify soft delete
    await db_session.refresh(shot)
    assert shot.status == "archived"
    assert shot.is_visible is False


@pytest.mark.asyncio
async def test_angle_shot_history(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    shot = AngleShot(
        name="Shot history",
        version=2,
    )
    db_session.add(shot)
    await db_session.commit()

    v1 = AngleShotVersion(
        angle_shot_id=shot.id,
        version=1,
        configuration={"pose": "standing"},
        change_note="Initial version",
    )
    v2 = AngleShotVersion(
        angle_shot_id=shot.id,
        version=2,
        configuration={"pose": "sitting"},
        change_note="Changed to sitting",
    )
    db_session.add_all([v1, v2])
    await db_session.commit()

    res = await client.get(f"/api/v1/angle-shots/{shot.id}/history", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    versions = res.json()["versions"]
    assert len(versions) == 2
    assert versions[0]["version"] == 2
    assert versions[0]["change_note"] == "Changed to sitting"
    assert versions[1]["version"] == 1


@pytest.mark.asyncio
async def test_restore_angle_shot_version(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    shot = AngleShot(
        name="Restorable Shot",
        framing="UPPER_BODY",
        pose="sitting",
        version=2,
    )
    db_session.add(shot)
    await db_session.commit()

    v1 = AngleShotVersion(
        angle_shot_id=shot.id,
        version=1,
        configuration={"framing": "FULL_BODY", "pose": "standing", "view_direction": "front"},
        change_note="v1",
    )
    v2 = AngleShotVersion(
        angle_shot_id=shot.id,
        version=2,
        configuration={"framing": "UPPER_BODY", "pose": "sitting", "view_direction": "back"},
        change_note="v2",
    )
    db_session.add_all([v1, v2])
    await db_session.commit()

    res = await client.post(
        f"/api/v1/angle-shots/{shot.id}/restore?version_number=1", headers=editor_headers
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["restored_from_version"] == 1
    assert res.json()["current_version"] == 3

    # Check restored state in DB
    await db_session.refresh(shot)
    assert shot.framing == "FULL_BODY"
    assert shot.pose == "standing"
    assert shot.view_direction == "front"


@pytest.mark.asyncio
async def test_check_compatibility(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    shot = AngleShot(
        name="Back View Baby Preset",
        category="BABY",
        framing="BACK",
        pose="SEATED",
    )
    db_session.add(shot)
    await db_session.commit()

    # Mismatched age group + back view without back reference checks
    payload = {
        "product_type": "JEWELRY",
        "fabric_type": "STIFF",
        "model_age_group": "ADULT",
        "has_back_reference": False,
    }

    res = await client.post(
        f"/api/v1/angle-shots/{shot.id}/compatibility-check",
        json=payload,
        headers=editor_headers,
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["compatible"] is False
    assert len(data["blocking_reasons"]) > 0
    # verify warnings are caught (back view warning, fabric warn, kids mismatch blocking)
    assert any("back_reference" in w.lower() for w in data["warnings"])
    assert any("distort" in w.lower() for w in data["warnings"])
    assert any("suitable" in r.lower() for r in data["blocking_reasons"])


# ========================== Worker Tests ========================

class MockSessionContext:
    def __init__(self, session):
        self.session = session
    async def __aenter__(self):
        return self.session
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.mark.asyncio
async def test_angle_shot_worker_extraction(client: AsyncClient, db_session: AsyncSession):
    shot = AngleShot(
        name="Custom Uploaded Reference",
        framing="FULL_BODY",
        pose="custom",
        status="queued",
        version=1,
    )
    db_session.add(shot)
    await db_session.commit()

    mock_task = MagicMock()

    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)):
        await _process_custom_angle_shot_async(mock_task, shot.id)

    # Verify properties updated in Celery task
    await db_session.refresh(shot)
    assert shot.status == "active"
    assert shot.version == 2
    assert shot.pose_map_url == "/poses/mock_" + str(shot.id) + ".json"
    assert shot.thumbnail_url == f"/thumbnails/angle_shot_{shot.id}.webp"

    # Verify version snapshot saved
    v_res = await db_session.execute(
        select(AngleShotVersion).where(
            AngleShotVersion.angle_shot_id == shot.id, AngleShotVersion.version == 2
        )
    )
    latest_version = v_res.scalars().first()
    assert latest_version is not None
    assert latest_version.change_note == "Custom pose extracted from reference image"


# ========================== Schema & Seeding Tests ========================

@pytest.mark.asyncio
async def test_validate_pose_preset_schema(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    # 1. Test valid payload
    valid_payload = {
        "preset_id": "ML-POSE-CAT-999",
        "version": "1.0.0",
        "family": "CATALOG_STANDING",
        "display_name": "Valid Test Pose",
        "body_yaw_deg": 45,
        "framing": "FULL_BODY",
        "qa_rule_codes": ["RULE_A", "RULE_B"],
        "status": "ACTIVE",
        "tier": "CORE",
        "risk_level": "LOW"
    }
    res = await client.post("/api/v1/angle-shots/validate", json=valid_payload, headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["valid"] is True

    # 2. Test invalid payload (missing display_name, body_yaw_deg out of range)
    invalid_payload = {
        "preset_id": "ML-POSE-CAT-999",
        "version": "1.0.0",
        "family": "CATALOG_STANDING",
        "body_yaw_deg": 250,
        "framing": "FULL_BODY",
        "qa_rule_codes": ["RULE_A"],
        "status": "ACTIVE"
    }
    res = await client.post("/api/v1/angle-shots/validate", json=invalid_payload, headers=editor_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "JSON schema validation failed" in res.json()["detail"]


@pytest.mark.asyncio
async def test_create_preset_with_schema_validation(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    # 1. Valid ML-POSE creation
    payload = {
        "name": "Front Angle Test",
        "code": "ML-POSE-CAT-101",
        "category": "CATALOG_STANDING",
        "framing": "FULL_BODY",
        "pose": "standing",
        "quality_rules": {
            "version": "1.0.0",
            "body_yaw_deg": "0",
            "qa_rule_codes": "RULE_A;RULE_B",
            "tier": "CORE",
            "risk_level": "LOW"
        }
    }
    res = await client.post("/api/v1/angle-shots", json=payload, headers=editor_headers)
    assert res.status_code == status.HTTP_201_CREATED

    # 2. Invalid ML-POSE creation (missing framing)
    invalid_payload = {
        "name": "Invalid Test",
        "code": "ML-POSE-CAT-102",
        "category": "CATALOG_STANDING",
        "quality_rules": {
            "version": "1.0.0",
            "body_yaw_deg": "0",
            "qa_rule_codes": "RULE_A",
            "tier": "CORE"
        }
    }
    res = await client.post("/api/v1/angle-shots", json=invalid_payload, headers=editor_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_seed_angle_shot_presets_integration(db_session: AsyncSession):
    # Run the seed function directly with current active session
    from seed_angle_shot_presets import seed as run_seed
    with patch("seed_angle_shot_presets.async_sessionmaker") as mock_maker:
        # Patch session context to return db_session
        mock_context = MagicMock()
        mock_context.__aenter__.return_value = db_session
        mock_maker.return_value = lambda: mock_context
        
        await run_seed()

    res = await db_session.execute(select(AngleShot).where(AngleShot.code == "ML-POSE-CAT-001"))
    shot = res.scalars().first()
    assert shot is not None
    assert shot.name == "Front Neutral"
    assert shot.is_premium is False
    assert shot.quality_rules["version"] == "1.0.0"
    assert "EVEN" in shot.quality_rules["weight_distribution"]


@pytest.mark.asyncio
async def test_list_angle_shots_advanced_and_facets(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    shot_a = AngleShot(
        name="Front Weight Left",
        code="ML-POSE-CAT-004",
        slug="front-weight-left",
        framing="FULL_BODY",
        pose="relaxed",
        view_direction="FRONT",
        age_groups=["ADULT", "TEEN"],
        tags=["lifestyle", "catalog"],
        is_custom=False,
        is_visible=True,
    )
    shot_b = AngleShot(
        name="Back Neutral",
        code="ML-POSE-CAT-042",
        slug="back-neutral",
        framing="FULL_BODY",
        pose="neutral",
        view_direction="BACK",
        age_groups=["ADULT"],
        tags=["fit"],
        is_custom=True,
        is_visible=True,
    )

    db_session.add_all([shot_a, shot_b])
    await db_session.commit()

    # 1. Test filtering by ageGroup
    res = await client.get("/api/v1/angle-shots?ageGroup=TEEN", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["code"] == "ML-POSE-CAT-004"

    # 2. Test filtering by source / SYSTEM
    res = await client.get("/api/v1/angle-shots?source=SYSTEM", headers=editor_headers)
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["code"] == "ML-POSE-CAT-004"

    # 3. Test filtering by source / CUSTOM
    res = await client.get("/api/v1/angle-shots?source=ORGANIZATION", headers=editor_headers)
    assert len(res.json()["items"]) == 1
    assert res.json()["items"][0]["code"] == "ML-POSE-CAT-042"

    # 4. Verify facets are computed
    res = await client.get("/api/v1/angle-shots", headers=editor_headers)
    facets = res.json()["facets"]
    assert facets["framing"]["FULL_BODY"] == 2
    assert facets["viewDirection"]["FRONT"] == 1
    assert facets["viewDirection"]["BACK"] == 1


@pytest.mark.asyncio
async def test_get_filter_facets_endpoint(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    
    shot = AngleShot(
        name="Test Shot Facet",
        framing="CLOSE_UP",
        tags=["special", "new-arrivals"],
        is_visible=True,
    )
    db_session.add(shot)
    await db_session.commit()

    res = await client.get("/api/v1/angle-shots/facets", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "productTypes" in data
    assert "ageGroups" in data
    assert "framings" in data
    assert "special" in data["tags"]


@pytest.mark.asyncio
async def test_reorder_and_bulk_update_endpoints(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    shot_a = AngleShot(name="Shot A", is_visible=True, sort_order=0)
    shot_b = AngleShot(name="Shot B", is_visible=True, sort_order=0)
    db_session.add_all([shot_a, shot_b])
    await db_session.commit()

    # 1. Test Reorder
    reorder_payload = {
        "orders": [
            {"id": shot_a.id, "sortOrder": 10},
            {"id": shot_b.id, "sortOrder": 20}
        ]
    }
    res = await client.post("/api/v1/angle-shots/admin/reorder", json=reorder_payload, headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    
    await db_session.refresh(shot_a)
    await db_session.refresh(shot_b)
    assert shot_a.sort_order == 10
    assert shot_b.sort_order == 20

    # 2. Test Bulk Update
    bulk_payload = {
        "ids": [shot_a.id, shot_b.id],
        "status": "ARCHIVED",
        "isVisible": False
    }
    res = await client.post("/api/v1/angle-shots/admin/bulk-update", json=bulk_payload, headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["updated_count"] == 2

    await db_session.refresh(shot_a)
    assert shot_a.status == "ARCHIVED"
    assert shot_a.is_visible is False


@pytest.mark.asyncio
async def test_custom_pose_endpoints(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")

    # 1. Request upload URL
    res = await client.post(
        "/api/v1/angle-shots/custom/upload-url",
        json={"fileName": "my-pose.png", "mimeType": "image/png", "fileSize": 1000},
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "uploadUrl" in data
    assert "referenceImageKey" in data

    # 2. Create custom preset
    create_payload = {
        "name": "My Custom Walk",
        "referenceImageKey": data["referenceImageKey"],
        "productTypes": ["DRESS"],
        "ageGroups": ["ADULT"],
        "requestedFraming": "FULL_BODY"
    }
    res = await client.post("/api/v1/angle-shots/custom", json=create_payload, headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "processing"
    
    # Verify in DB
    db_res = await db_session.execute(select(AngleShot).where(AngleShot.id == res.json()["id"]))
    shot = db_res.scalars().first()
    assert shot is not None
    assert shot.pose == "CUSTOM"
    assert shot.reference_image_url.endswith(data["referenceImageKey"])


@pytest.mark.asyncio
async def test_apply_angle_shots_endpoint(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    brand = test_data["brand"]

    # 1. Create a Campaign and an Asset
    campaign = Campaign(name="Fall Catalog", description="Outerwear launch", brand_id=brand.id)
    asset = Asset(brand_id=brand.id, filename="jacket.jpg", storage_path="/path/jacket.jpg", asset_type="product")
    db_session.add_all([campaign, asset])
    await db_session.commit()

    # Link asset to campaign
    from app.models.db import CampaignAsset
    camp_asset = CampaignAsset(campaign_id=campaign.id, asset_id=asset.id)
    db_session.add(camp_asset)
    
    # Seed Angle Shot
    shot = AngleShot(
        name="Front Neutral Stance",
        code="ML-POSE-CAT-001",
        framing="FULL_BODY",
        pose="neutral",
        view_direction="FRONT",
        is_visible=True,
    )
    db_session.add(shot)
    await db_session.commit()

    # 2. Apply Angle Shot to Campaign
    apply_payload = {
        "angleShotIds": ["ML-POSE-CAT-001"],
        "applyMode": "ALL_PRODUCTS",
        "productIds": []
    }
    res = await client.post(
        f"/api/v1/campaigns/{campaign.id}/angle-shots/apply",
        json=apply_payload,
        headers=editor_headers
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["applied_count"] == 1

    # 3. Verify ShootAngleShot record is snapshot-copied
    db_res = await db_session.execute(
        select(ShootAngleShot).where(
            ShootAngleShot.shoot_id == campaign.id,
            ShootAngleShot.shoot_product_id == str(asset.id),
            ShootAngleShot.angle_shot_id == shot.id
        )
    )
    shoot_shot = db_res.scalars().first()
    assert shoot_shot is not None
    assert shoot_shot.configuration["framing"] == "FULL_BODY"
    assert shoot_shot.configuration["view_direction"] == "FRONT"


