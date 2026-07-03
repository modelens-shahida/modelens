from fastapi import APIRouter, HTTPException, Depends, status, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, Character, Brand, BrandMember, User, CreditTransaction
from app.middleware.auth import get_current_user
from app.worker import process_training_job

router = APIRouter(
    prefix="/api/v1/characters",
    tags=["Characters"],
)

# ========================== Request / Response Schemas =====================

class CharacterCreateRequest(BaseModel):
    brand_id: int
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(...)
    image_path: str = Field(..., min_length=1, max_length=1000)

class CharacterResponse(BaseModel):
    id: int
    brand_id: int
    name: str
    description: str
    image_path: str

    model_config = {"from_attributes": True}

# ========================== Helper Functions ===============================

async def get_accessible_brand_ids(user_id: int, db: AsyncSession) -> set[int]:
    owned_query = select(Brand.id).where(Brand.owner_id == user_id)
    owned_result = await db.execute(owned_query)
    accessible_brand_ids = set(owned_result.scalars().all())

    member_query = select(BrandMember.brand_id).where(BrandMember.user_id == user_id)
    member_result = await db.execute(member_query)
    accessible_brand_ids.update(member_result.scalars().all())
    
    return accessible_brand_ids

# ========================== Characters CRUD ================================

@router.post("", status_code=status.HTTP_201_CREATED, response_model=CharacterResponse)
async def create_character(
    payload: CharacterCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new character template under an accessible brand workspace.
    """
    accessible_brands = await get_accessible_brand_ids(current_user.id, db)
    if payload.brand_id not in accessible_brands:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this brand workspace."
        )

    character = Character(
        brand_id=payload.brand_id,
        name=payload.name,
        description=payload.description,
        image_path=payload.image_path
    )
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character

@router.get("", response_model=List[CharacterResponse])
async def list_characters(
    brand_id: Optional[int] = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all characters accessible to the caller.
    If brand_id is provided, filters to that brand (if accessible).
    """
    accessible_brands = await get_accessible_brand_ids(current_user.id, db)
    if not accessible_brands:
        return []

    query = select(Character)
    if brand_id is not None:
        if brand_id not in accessible_brands:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this brand workspace."
            )
        query = query.where(Character.brand_id == brand_id)
    else:
        query = query.where(Character.brand_id.in_(list(accessible_brands)))

    result = await db.execute(query.limit(limit).offset(offset))
    return list(result.scalars().all())


# ========================== Extended CRUD ==================================

class CharacterUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    image_path: Optional[str] = Field(None, min_length=1, max_length=1000)


async def get_user_role_in_brand(user_id: int, brand_id: int, db: AsyncSession) -> str:
    """Returns 'owner', 'member', or 'none'"""
    owner_query = select(Brand).where(Brand.id == brand_id, Brand.owner_id == user_id)
    owner_result = await db.execute(owner_query)
    if owner_result.scalars().first():
        return "owner"
    member_query = select(BrandMember).where(
        BrandMember.brand_id == brand_id,
        BrandMember.user_id == user_id
    )
    member_result = await db.execute(member_query)
    member = member_result.scalars().first()
    if member:
        return member.role
    return "none"


@router.get("/{character_id}", response_model=CharacterResponse)
async def get_character(
    character_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a specific character by ID."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalars().first()
    if not character:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found.")
    accessible_brands = await get_accessible_brand_ids(current_user.id, db)
    if character.brand_id not in accessible_brands:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this character.")
    return character


@router.patch("/{character_id}", response_model=CharacterResponse)
async def update_character(
    character_id: int,
    payload: CharacterUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update character fields. Requires at least editor role."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalars().first()
    if not character:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found.")
    role = await get_user_role_in_brand(current_user.id, character.brand_id, db)
    if role == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this brand workspace.")
    if role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot update characters.")
    if payload.name is not None:
        character.name = payload.name
    if payload.description is not None:
        character.description = payload.description
    if payload.image_path is not None:
        character.image_path = payload.image_path
    await db.commit()
    await db.refresh(character)
    return character


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_character(
    character_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a character. Requires owner or admin role."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalars().first()
    if not character:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found.")
    role = await get_user_role_in_brand(current_user.id, character.brand_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners or admins can delete characters.")
    await db.delete(character)
    await db.commit()


# ========================== Character Versions & Embeddings ========

from app.models.db import CharacterVersion, CharacterEmbedding

class CharacterVersionCreateRequest(BaseModel):
    version_number: Optional[int] = None
    prompt_trigger: Optional[str] = None
    reference_image_path: Optional[str] = Field(None, max_length=1000)
    validation_image_path: Optional[str] = Field(None, max_length=1000)
    config_overrides: Optional[dict] = Field(default_factory=dict)

class CharacterVersionResponse(BaseModel):
    id: int
    character_id: int
    version_number: int
    prompt_trigger: Optional[str]
    reference_image_path: Optional[str]
    validation_image_path: Optional[str]
    config_overrides: dict
    model_config = {"from_attributes": True}

class CharacterEmbeddingCreateRequest(BaseModel):
    embedding: list[float] = Field(..., description="1536-dimensional vector")
    tag: str = Field(..., min_length=1, max_length=255)

class CharacterEmbeddingResponse(BaseModel):
    id: int
    character_id: int
    version_id: int
    tag: str
    model_config = {"from_attributes": True}


@router.post("/{character_id}/versions", status_code=status.HTTP_201_CREATED, response_model=CharacterVersionResponse)
async def create_character_version(
    character_id: int,
    payload: CharacterVersionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new version for a character. Requires editor role or above."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalars().first()
    if not character:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found.")

    role = await get_user_role_in_brand(current_user.id, character.brand_id, db)
    if role == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this brand workspace.")
    if role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot create character versions.")

    # Auto-increment version_number if not specified
    if payload.version_number is None:
        count_result = await db.execute(
            select(CharacterVersion).where(CharacterVersion.character_id == character_id)
        )
        existing = count_result.scalars().all()
        version_number = len(existing) + 1
    else:
        version_number = payload.version_number

    version = CharacterVersion(
        character_id=character_id,
        version_number=version_number,
        prompt_trigger=payload.prompt_trigger,
        reference_image_path=payload.reference_image_path,
        validation_image_path=payload.validation_image_path,
        config_overrides=payload.config_overrides or {},
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


@router.get("/{character_id}/versions", response_model=List[CharacterVersionResponse])
async def list_character_versions(
    character_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all versions for a given character."""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalars().first()
    if not character:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found.")

    accessible_brands = await get_accessible_brand_ids(current_user.id, db)
    if character.brand_id not in accessible_brands:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this character.")

    versions_result = await db.execute(
        select(CharacterVersion).where(CharacterVersion.character_id == character_id)
    )
    return list(versions_result.scalars().all())


@router.post("/{character_id}/versions/{version_id}/embeddings", status_code=status.HTTP_201_CREATED, response_model=CharacterEmbeddingResponse)
async def create_character_embedding(
    character_id: int,
    version_id: int,
    payload: CharacterEmbeddingCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Associate a 1536-dim embedding with a character version."""
    # Validate character exists and accessible
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalars().first()
    if not character:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found.")

    accessible_brands = await get_accessible_brand_ids(current_user.id, db)
    if character.brand_id not in accessible_brands:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this character.")

    # Validate version exists
    version_result = await db.execute(
        select(CharacterVersion).where(
            CharacterVersion.id == version_id,
            CharacterVersion.character_id == character_id
        )
    )
    version = version_result.scalars().first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character version not found.")

    # Validate embedding dimensions
    if len(payload.embedding) != 1536:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Embedding must be exactly 1536 dimensions. Got {len(payload.embedding)}."
        )

    embedding = CharacterEmbedding(
        character_id=character_id,
        version_id=version_id,
        embedding=payload.embedding,
        tag=payload.tag,
    )
    db.add(embedding)
    await db.commit()
    await db.refresh(embedding)
    return embedding


# ========================== Character Training API =================

from app.models.db import AIJob

class TrainingRequest(BaseModel):
    version_number: int = Field(default=1, ge=1)
    training_assets: List[int] = Field(..., min_length=1, description="List of Asset IDs")
    hyperparameters: dict = Field(default_factory=lambda: {
        "learning_rate": 0.0001,
        "max_epochs": 10,
        "batch_size": 2
    })

class TrainingJobResponse(BaseModel):
    job_id: int
    character_id: int
    status: str
    credits_remaining: int
    model_config = {"from_attributes": True}


@router.post("/{character_id}/train", status_code=status.HTTP_201_CREATED, response_model=TrainingJobResponse)
async def train_character(
    character_id: int,
    payload: TrainingRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a character LoRA training job.
    Requires editor role. Deducts 10 credits on submission.
    """
    from app.models.db import Asset

    # 1. Verify character exists
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalars().first()
    if not character:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character not found.")

    # 2. RBAC check — editor or above
    role = await get_user_role_in_brand(current_user.id, character.brand_id, db)
    if role == "none":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have access to this brand workspace.")
    if role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Viewers cannot submit training jobs.")

    # 3. Validate training assets
    for asset_id in payload.training_assets:
        asset_result = await db.execute(select(Asset).where(Asset.id == asset_id))
        asset = asset_result.scalars().first()
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Asset {asset_id} not found.")
        if asset.brand_id != character.brand_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Asset {asset_id} does not belong to this brand.")
        if asset.asset_type != "image":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Asset {asset_id} is not an image.")

    # 4. Credit check and deduction (10 credits)
    user_result = await db.execute(select(User).where(User.id == current_user.id))
    user = user_result.scalars().first()
    if user.credits < 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Insufficient credits. Required: 10, Remaining: {user.credits}")
    user.credits -= 10
    credit_txn = CreditTransaction(
        user_id=current_user.id,
        amount=-10,
        transaction_type="spend",
        reference_type="job",
        balance_after=user.credits,
        description="Character LoRA training job credit deduction",
    )
    db.add(credit_txn)

    from app.routers.credits import _trigger_low_credit_warning_if_needed
    await _trigger_low_credit_warning_if_needed(db, user)

    # 5. Create AIJob
    job = AIJob(
        user_id=current_user.id,
        brand_id=character.brand_id,
        status="pending",
        job_type="character_training",
        inputs={
            "character_id": character_id,
            "version_number": payload.version_number,
            "training_assets": payload.training_assets,
            "hyperparameters": payload.hyperparameters,
        },
        outputs={},
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    await db.refresh(user)

    # 6. Enqueue background task
    process_training_job.delay(job.id)

    return TrainingJobResponse(
        job_id=job.id,
        character_id=character_id,
        status=job.status,
        credits_remaining=user.credits,
    )


@router.get("/versions/{version_id}/metrics")
async def get_character_version_metrics(
    version_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get MLflow metrics for a character version.
    Requires Admin or Owner role.
    """
    result = await db.execute(
        select(CharacterVersion).where(CharacterVersion.id == version_id)
    )
    version = result.scalars().first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Character version not found.")

    # Get character to check brand access
    char_result = await db.execute(select(Character).where(Character.id == version.character_id))
    character = char_result.scalars().first()

    role = await get_user_role_in_brand(current_user.id, character.brand_id, db)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Admin or Owner role to view training metrics.")

    if not version.mlflow_run_id:
        return {
            "version_id": version_id,
            "mlflow_run_id": None,
            "message": "No MLflow run associated with this version.",
            "params": {},
            "metrics": {},
            "artifact_uri": None,
        }

    try:
        import mlflow
        from app.config import settings
        mlflow.set_tracking_uri(settings.MLFLOW_URI)
        client = mlflow.tracking.MlflowClient()
        run = client.get_run(version.mlflow_run_id)

        return {
            "version_id": version_id,
            "mlflow_run_id": version.mlflow_run_id,
            "params": run.data.params,
            "metrics": run.data.metrics,
            "artifact_uri": run.info.artifact_uri,
            "status": run.info.status,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to retrieve MLflow metrics: {str(e)}"
        )
