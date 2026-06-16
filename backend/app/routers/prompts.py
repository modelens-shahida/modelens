from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.db import get_db, PromptTemplate, User
from app.middleware.auth import get_current_user

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

@router.post("", status_code=status.HTTP_201_CREATED, response_model=PromptResponse)
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

@router.get("", response_model=List[PromptResponse])
async def list_prompts(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all prompt templates.
    """
    query = select(PromptTemplate)
    result = await db.execute(query)
    return list(result.scalars().all())


# ========================== Extended CRUD ==================================

from typing import Optional
from fastapi import HTTPException


class PromptUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    prompt_text: Optional[str] = Field(None, min_length=1)


@router.get("/{prompt_id}", response_model=PromptResponse)
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


@router.patch("/{prompt_id}", response_model=PromptResponse)
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


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
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
