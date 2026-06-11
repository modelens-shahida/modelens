import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import Asset, Campaign, CampaignAsset, CampaignWorkflow

@pytest.mark.asyncio
async def test_campaign_crud_and_rbac(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    
    # 1. Create campaign as editor (Should succeed)
    editor_headers = test_data["get_headers"]("editor")
    create_payload = {
        "brand_id": brand.id,
        "name": "Winter Collection",
        "description": "Campaign for winter coats"
    }
    
    res = await client.post("/api/v1/campaigns", json=create_payload, headers=editor_headers)
    assert res.status_code == 201
    campaign_data = res.json()
    assert campaign_data["name"] == "Winter Collection"
    assert campaign_data["description"] == "Campaign for winter coats"
    campaign_id = campaign_data["id"]

    # 2. Try to create campaign as viewer (Should fail - 403)
    viewer_headers = test_data["get_headers"]("viewer")
    res = await client.post("/api/v1/campaigns", json=create_payload, headers=viewer_headers)
    assert res.status_code == 403

    # 3. Read campaign details as viewer (Should succeed)
    res = await client.get(f"/api/v1/campaigns/{campaign_id}", headers=viewer_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Winter Collection"

    # 4. Read campaign details as non-member (Should fail - 403)
    nonmember_headers = test_data["get_headers"]("nonmember")
    res = await client.get(f"/api/v1/campaigns/{campaign_id}", headers=nonmember_headers)
    assert res.status_code == 403

    # 5. List campaigns as viewer (Should succeed and include the campaign)
    res = await client.get(f"/api/v1/campaigns?brand_id={brand.id}", headers=viewer_headers)
    assert res.status_code == 200
    campaign_list = res.json()
    assert len(campaign_list) >= 1
    assert any(c["id"] == campaign_id for c in campaign_list)

    # 6. Update campaign as editor (Should succeed)
    update_payload = {
        "name": "Winter Jackets Collection",
        "description": "Updated winter description"
    }
    res = await client.patch(f"/api/v1/campaigns/{campaign_id}", json=update_payload, headers=editor_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Winter Jackets Collection"

    # 7. Update campaign as viewer (Should fail - 403)
    res = await client.patch(f"/api/v1/campaigns/{campaign_id}", json=update_payload, headers=viewer_headers)
    assert res.status_code == 403

    # 8. Delete campaign as viewer (Should fail - 403)
    res = await client.delete(f"/api/v1/campaigns/{campaign_id}", headers=viewer_headers)
    assert res.status_code == 403

    # 9. Delete campaign as editor (Should succeed - 204)
    res = await client.delete(f"/api/v1/campaigns/{campaign_id}", headers=editor_headers)
    assert res.status_code == 204

    # 10. Verify campaign is deleted
    res = await client.get(f"/api/v1/campaigns/{campaign_id}", headers=editor_headers)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_campaign_asset_linking(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    other_brand = test_data["other_brand"]
    editor_headers = test_data["get_headers"]("editor")
    
    # Pre-requisite: Create a campaign
    campaign = Campaign(brand_id=brand.id, name="Spring Promo", description="Promo for spring sales")
    db_session.add(campaign)
    await db_session.commit()
    await db_session.refresh(campaign)
    
    # Pre-requisite: Create assets
    # Asset 1 in same brand
    asset_same = Asset(
        brand_id=brand.id,
        name="banner.png",
        filename="banner.png",
        storage_path="/uploads/banner.png",
        asset_type="image",
        meta={"status": "active"}
    )
    # Asset 2 in other brand
    asset_diff = Asset(
        brand_id=other_brand.id,
        name="logo.png",
        filename="logo.png",
        storage_path="/uploads/logo.png",
        asset_type="image",
        meta={"status": "active"}
    )
    db_session.add(asset_same)
    db_session.add(asset_diff)
    await db_session.commit()
    await db_session.refresh(asset_same)
    await db_session.refresh(asset_diff)

    # 1. Link asset in same brand (Should succeed)
    res = await client.post(f"/api/v1/campaigns/{campaign.id}/assets/{asset_same.id}", headers=editor_headers)
    assert res.status_code == 201
    assert "successfully linked" in res.json()["message"]

    # 2. Verify link exists in DB
    query = select(CampaignAsset).where(
        CampaignAsset.campaign_id == campaign.id,
        CampaignAsset.asset_id == asset_same.id
    )
    db_res = await db_session.execute(query)
    assert db_res.scalars().first() is not None

    # 3. Attempt to link asset from different brand (Should fail - 400)
    res = await client.post(f"/api/v1/campaigns/{campaign.id}/assets/{asset_diff.id}", headers=editor_headers)
    assert res.status_code == 400
    assert "same brand" in res.json()["detail"]

    # 4. Link same asset again (Should return notice message)
    res = await client.post(f"/api/v1/campaigns/{campaign.id}/assets/{asset_same.id}", headers=editor_headers)
    assert res.status_code == 201
    assert "already linked" in res.json()["message"]

    # 5. Unlink asset (Should succeed)
    res = await client.delete(f"/api/v1/campaigns/{campaign.id}/assets/{asset_same.id}", headers=editor_headers)
    assert res.status_code == 200
    assert "successfully unlinked" in res.json()["message"]

    # 6. Verify link is deleted from DB
    db_res = await db_session.execute(query)
    assert db_res.scalars().first() is None


@pytest.mark.asyncio
async def test_campaign_workflow_linking(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    brand = test_data["brand"]
    workflow = test_data["workflow"]
    editor_headers = test_data["get_headers"]("editor")
    
    # Pre-requisite: Create a campaign
    campaign = Campaign(brand_id=brand.id, name="Autumn Blast", description="Autumn discounts")
    db_session.add(campaign)
    await db_session.commit()
    await db_session.refresh(campaign)

    # 1. Link workflow template (Should succeed)
    res = await client.post(f"/api/v1/campaigns/{campaign.id}/workflows/{workflow.id}", headers=editor_headers)
    assert res.status_code == 201
    assert "successfully linked" in res.json()["message"]

    # 2. Verify link in DB
    query = select(CampaignWorkflow).where(
        CampaignWorkflow.campaign_id == campaign.id,
        CampaignWorkflow.workflow_id == workflow.id
    )
    db_res = await db_session.execute(query)
    assert db_res.scalars().first() is not None

    # 3. Link workflow again (Should return notice message)
    res = await client.post(f"/api/v1/campaigns/{campaign.id}/workflows/{workflow.id}", headers=editor_headers)
    assert res.status_code == 201
    assert "already linked" in res.json()["message"]

    # 4. Unlink workflow template (Should succeed)
    res = await client.delete(f"/api/v1/campaigns/{campaign.id}/workflows/{workflow.id}", headers=editor_headers)
    assert res.status_code == 200
    assert "successfully unlinked" in res.json()["message"]

    # 5. Verify link deleted from DB
    db_res = await db_session.execute(query)
    assert db_res.scalars().first() is None
