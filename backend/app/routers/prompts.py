from fastapi import APIRouter, Depends, status, Query
from pydantic import BaseModel, Field
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, PromptTemplate, User
from app.middleware.auth import get_current_user
from app.api_docs import error_responses, limit_query, offset_query

router = APIRouter(
    prefix="/api/v1/prompts",
    tags=["Prompts"],
)

# ========================== Request / Response Schemas =====================

class PromptCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    prompt_text: str = Field(..., min_length=1)

class PromptResponse(BaseModel):
    id: int
    name: str
    prompt_text: str

    model_config = {"from_attributes": True}

# ========================== Prompts CRUD ===================================

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=PromptResponse,
    summary="Create a prompt template",
    description="Create a new prompt template.",
    response_description="The created prompt template.",
    operation_id="create_prompt",
    responses=error_responses(401, 422),
)
async def create_prompt(
    payload: PromptCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new prompt template.
    """
    prompt = PromptTemplate(
        name=payload.name,
        prompt_text=payload.prompt_text
    )
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return prompt

@router.get(
    "",
    response_model=List[PromptResponse],
    summary="List prompt templates",
    description="List all prompt templates.",
    response_description="A page of prompt templates.",
    operation_id="list_prompts",
    responses=error_responses(401, 422),
)
async def list_prompts(
    limit: int = limit_query(20, le=100),
    offset: int = offset_query(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all prompt templates.
    """
    query = select(PromptTemplate)
    result = await db.execute(query.limit(limit).offset(offset))
    return list(result.scalars().all())


# ========================== Extended CRUD ==================================

from typing import Optional
from fastapi import HTTPException


class PromptUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    prompt_text: Optional[str] = Field(None, min_length=1)


@router.get(
    "/{prompt_id}",
    response_model=PromptResponse,
    summary="Get a prompt template",
    description="Retrieve a specific prompt template by ID.",
    response_description="The requested prompt template.",
    operation_id="get_prompt",
    responses=error_responses(401, 404, 422),
)
async def get_prompt(
    prompt_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a specific prompt template by ID."""
    result = await db.execute(select(PromptTemplate).where(PromptTemplate.id == prompt_id))
    prompt = result.scalars().first()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found.")
    return prompt


@router.patch(
    "/{prompt_id}",
    response_model=PromptResponse,
    summary="Update a prompt template",
    description="Update a prompt template.",
    response_description="The updated prompt template.",
    operation_id="update_prompt",
    responses=error_responses(401, 404, 422),
)
async def update_prompt(
    prompt_id: int,
    payload: PromptUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a prompt template."""
    result = await db.execute(select(PromptTemplate).where(PromptTemplate.id == prompt_id))
    prompt = result.scalars().first()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found.")
    if payload.name is not None:
        prompt.name = payload.name
    if payload.prompt_text is not None:
        prompt.prompt_text = payload.prompt_text
    await db.commit()
    await db.refresh(prompt)
    return prompt


@router.delete(
    "/{prompt_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a prompt template",
    description="Delete a prompt template.",
    response_description="Prompt template deleted; no content returned.",
    operation_id="delete_prompt",
    responses=error_responses(401, 404, 422),
)
async def delete_prompt(
    prompt_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a prompt template."""
    result = await db.execute(select(PromptTemplate).where(PromptTemplate.id == prompt_id))
    prompt = result.scalars().first()
    if not prompt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found.")
    await db.delete(prompt)
    await db.commit()
