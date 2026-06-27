import json
import pytest
from unittest.mock import patch, AsyncMock
from fastapi import status
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.db import CreditTransaction, User, AIJob, Character, CharacterVersion, Asset
from app.worker import _process_generation_job_async, _process_workflow_job_async, _process_training_job_async

@pytest.mark.asyncio
async def test_credit_history_auth_required(client: AsyncClient):
    res = await client.get("/api/v1/credits/history")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_get_credit_balance(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get("/api/v1/credits/balance", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert "balance" in res.json()
    assert "low_credits" in res.json()


@pytest.mark.asyncio
async def test_low_credits_flag(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    user.credits = 5
    await db_session.commit()
    res = await client.get("/api/v1/credits/balance", headers=editor_headers)
    assert res.json()["low_credits"] is True


@pytest.mark.asyncio
async def test_credit_history_empty(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    res = await client.get("/api/v1/credits/history", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_mock_purchase_starter(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    user_result = await db_session.execute(select(User).where(User.id == editor_user.id))
    user = user_result.scalars().first()
    starting_credits = user.credits
    res = await client.post("/api/v1/credits/mock-purchase", json={"package": "starter"}, headers=editor_headers)
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["credits_added"] == 100
    assert res.json()["new_balance"] == starting_credits + 100


@pytest.mark.asyncio
async def test_mock_purchase_invalid_package(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    res = await client.post("/api/v1/credits/mock-purchase", json={"package": "invalid"}, headers=editor_headers)
    assert res.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_admin_adjust_unauthorized(client: AsyncClient, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    res = await client.post("/api/v1/credits/admin-adjust", json={
        "target_user_id": editor_user.id, "amount": 100, "description": "Test"
    }, headers=editor_headers)
    assert res.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_admin_adjust_success(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    owner_headers = test_data["get_headers"]("owner")
    owner_user = test_data["users"]["owner"]
    editor_user = test_data["users"]["editor"]
    editor_id = editor_user.id
    
    # Elevate owner user to system-wide admin for authorization checks
    owner_result = await db_session.execute(select(User).where(User.id == owner_user.id))
    db_owner = owner_result.scalars().first()
    db_owner.role = "admin"
    await db_session.commit()
    
    # Pre-read editor user credits
    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    starting_credits = user.credits
    
    res = await client.post("/api/v1/credits/admin-adjust", json={
        "target_user_id": editor_id, "amount": 100, "description": "Admin topup"
    }, headers=owner_headers)
    assert res.status_code == status.HTTP_200_OK
    
    # Reload from DB and verify
    await db_session.close()
    db_session.expire_all()
    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    assert user.credits == starting_credits + 100
    
    # Verify transaction row
    txn_result = await db_session.execute(
        select(CreditTransaction).where(CreditTransaction.user_id == editor_id, CreditTransaction.transaction_type == "top_up")
    )
    txn = txn_result.scalars().first()
    assert txn is not None
    assert txn.amount == 100
    assert txn.balance_after == starting_credits + 100


@pytest.mark.asyncio
async def test_credit_history_pagination(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    editor_id = editor_user.id
    
    # Add 5 transactions
    for i in range(5):
        db_session.add(CreditTransaction(
            user_id=editor_id,
            amount=-1,
            transaction_type="spend",
            reference_type="job",
            balance_after=100 - i,
            description=f"Tx {i}"
        ))
    await db_session.commit()
    
    # Limit 2
    res = await client.get("/api/v1/credits/history?limit=2&offset=0", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) == 2
    
    # Offset 4
    res = await client.get("/api/v1/credits/history?limit=2&offset=4", headers=editor_headers)
    assert res.status_code == status.HTTP_200_OK
    assert len(res.json()) == 1


@pytest.mark.asyncio
async def test_job_generation_deducts_and_logs_credit(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    editor_id = editor_user.id
    brand_id = test_data["brand"].id
    wf_id = test_data["workflow"].id
    
    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    starting_credits = user.credits
    
    with patch("app.routers.jobs.process_generation_job.delay"):
        res = await client.post("/api/v1/jobs/generate", json={
            "brand_id": brand_id,
            "workflow_template_id": wf_id,
            "inputs": {"prompt": "test prompt"}
        }, headers=editor_headers)
        assert res.status_code == status.HTTP_201_CREATED
        
        # Verify credits and transaction
        await db_session.close()
        db_session.expire_all()
        user_result = await db_session.execute(select(User).where(User.id == editor_id))
        user = user_result.scalars().first()
        assert user.credits == starting_credits - 1
        
        txn_result = await db_session.execute(
            select(CreditTransaction).where(CreditTransaction.user_id == editor_id, CreditTransaction.transaction_type == "spend")
        )
        txn = txn_result.scalars().first()
        assert txn is not None
        assert txn.amount == -1
        assert txn.balance_after == starting_credits - 1


@pytest.mark.asyncio
async def test_job_workflow_deducts_and_logs_credit(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    editor_id = editor_user.id
    brand_id = test_data["brand"].id
    
    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    starting_credits = user.credits
    
    with patch("app.routers.jobs.process_workflow_job.delay"):
        res = await client.post("/api/v1/jobs/workflow", json={
            "brand_id": brand_id,
            "workflow_type": "on_model_replacement",
            "inputs": {"prompt": "test workflow prompt"}
        }, headers=editor_headers)
        assert res.status_code == status.HTTP_201_CREATED
        
        # Verify credits and transaction
        await db_session.close()
        db_session.expire_all()
        user_result = await db_session.execute(select(User).where(User.id == editor_id))
        user = user_result.scalars().first()
        assert user.credits == starting_credits - 1
        
        txn_result = await db_session.execute(
            select(CreditTransaction).where(CreditTransaction.user_id == editor_id, CreditTransaction.transaction_type == "spend")
        )
        txn = txn_result.scalars().first()
        assert txn is not None
        assert txn.amount == -1
        assert txn.balance_after == starting_credits - 1


@pytest.mark.asyncio
async def test_character_training_deducts_and_logs_credits(client: AsyncClient, db_session: AsyncSession, test_data: dict):
    editor_headers = test_data["get_headers"]("editor")
    editor_user = test_data["users"]["editor"]
    editor_id = editor_user.id
    brand_id = test_data["brand"].id
    
    # Create character
    char = Character(brand_id=brand_id, name="Test Char", description="female model", image_path="/uploads/test_char.png")
    db_session.add(char)
    await db_session.commit()
    char_id = char.id
    
    # Create asset for training
    asset = Asset(
        brand_id=brand_id,
        name="test_image.png",
        filename="test_image.png",
        storage_path="/uploads/test_image.png",
        asset_type="image",
        status="active",
        meta={"prompt": "test asset"}
    )
    db_session.add(asset)
    await db_session.commit()
    asset_id = asset.id
    
    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    starting_credits = user.credits
    
    with patch("app.routers.characters.process_training_job.delay"):
        res = await client.post(f"/api/v1/characters/{char_id}/train", json={
            "version_number": 1,
            "training_assets": [asset_id]
        }, headers=editor_headers)
        assert res.status_code == status.HTTP_201_CREATED
        
        # Verify credits and transaction
        await db_session.close()
        db_session.expire_all()
        user_result = await db_session.execute(select(User).where(User.id == editor_id))
        user = user_result.scalars().first()
        assert user.credits == starting_credits - 10
        
        txn_result = await db_session.execute(
            select(CreditTransaction).where(
                CreditTransaction.user_id == editor_id, 
                CreditTransaction.transaction_type == "spend",
                CreditTransaction.amount == -10
            )
        )
        txn = txn_result.scalars().first()
        assert txn is not None
        assert txn.balance_after == starting_credits - 10


@pytest.mark.asyncio
async def test_job_failures_refund_and_log(db_session: AsyncSession, test_data: dict):
    editor_user = test_data["users"]["editor"]
    editor_id = editor_user.id
    brand_id = test_data["brand"].id
    wf_id = test_data["workflow"].id
    
    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    starting_credits = user.credits
    
    gen_job = AIJob(user_id=editor_id, brand_id=brand_id, workflow_template_id=wf_id, status="pending", job_type="generation", inputs={}, outputs={})
    wf_job = AIJob(user_id=editor_id, brand_id=brand_id, workflow_template_id=None, status="pending", job_type="workflow", inputs={}, outputs={})
    
    char = Character(brand_id=brand_id, name="Test Char", description="female model", image_path="/uploads/test_char.png")
    db_session.add(char)
    await db_session.commit()
    char_id = char.id
    train_job = AIJob(user_id=editor_id, brand_id=brand_id, status="pending", job_type="character_training", inputs={"character_id": char_id, "version_number": 1}, outputs={})
    
    db_session.add(gen_job)
    db_session.add(wf_job)
    db_session.add(train_job)
    await db_session.commit()
    
    gen_id = gen_job.id
    wf_id = wf_job.id
    train_id = train_job.id
    
    from app.worker import async_session_maker
    class MockSessionContext:
        def __init__(self, session):
            self.session = session
        async def __aenter__(self):
            return self.session
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
            
    # Mock generation failure
    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.worker._generate_image", side_effect=Exception("API Error")):
        await _process_generation_job_async(gen_id, retries=3, max_retries=3)
        
    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    assert user.credits == starting_credits + 1
    
    # Mock workflow failure
    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.worker.redis_client"), \
         patch("app.worker._publish_brand_event"), \
         patch("app.worker._generate_image", side_effect=Exception("Workflow Error")):
        await _process_workflow_job_async(wf_id, retries=3, max_retries=3)
            
    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    assert user.credits == starting_credits + 2
    
    # Mock character training failure
    with patch("app.worker.async_session_maker", return_value=MockSessionContext(db_session)), \
         patch("app.worker.storage_service"), \
         patch("app.worker.asyncio.sleep", side_effect=Exception("Simulated training error")):
        await _process_training_job_async(train_id, retries=3, max_retries=3)
            
    user_result = await db_session.execute(select(User).where(User.id == editor_id))
    user = user_result.scalars().first()
    assert user.credits == starting_credits + 12
    
    # Check that transaction logs exist for all three refunds
    txns = (await db_session.execute(
        select(CreditTransaction).where(CreditTransaction.user_id == editor_id, CreditTransaction.transaction_type == "refund")
    )).scalars().all()
    assert len(txns) == 3
    amounts = {t.amount for t in txns}
    assert amounts == {1, 10}
