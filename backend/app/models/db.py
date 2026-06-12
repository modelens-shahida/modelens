from datetime import datetime
from typing import Optional
import sqlalchemy as sa
from sqlalchemy import (
    String,
    Integer,
    DateTime,
    ForeignKey,
    Text,
    Boolean,
    UniqueConstraint,
    Index,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
from app.config import settings

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50))
    credits: Mapped[int] = mapped_column(Integer, default=100)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )

    owner = relationship("User")

class BrandMember(Base):
    __tablename__ = "brand_members"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(50), default="member")

    brand = relationship("Brand")
    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("brand_id", "user_id", name="uq_brand_member"),
    )

class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    filename: Mapped[str] = mapped_column(String(500))
    storage_path: Mapped[str] = mapped_column(String(1000))
    asset_type: Mapped[str] = mapped_column(String(100))
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    brand = relationship("Brand")
    tags = relationship("AssetTag", back_populates="asset", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        Index("idx_assets_metadata_gin", "metadata", postgresql_using="gin"),
        Index(
            "idx_assets_name_metadata_fts",
            func.to_tsvector(
                "english",
                func.coalesce(sa.column("name"), "") + " " + func.coalesce(sa.cast(sa.column("metadata"), sa.Text), "")
            ),
            postgresql_using="gin"
        ),
    )

class AssetTag(Base):
    __tablename__ = "asset_tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE")
    )
    tag: Mapped[str] = mapped_column(String(255), index=True)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(1536), nullable=True)

    asset = relationship("Asset", back_populates="tags")


    __table_args__ = (
        Index(
            "idx_asset_tags_embedding_ivfflat",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_with={"lists": 100},
            postgresql_ops={"embedding": "vector_cosine_ops"}
        ),
    )

class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)

    brand = relationship("Brand")


class CampaignAsset(Base):
    __tablename__ = "campaign_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE")
    )

    campaign = relationship("Campaign")
    asset = relationship("Asset")

    __table_args__ = (
        UniqueConstraint("campaign_id", "asset_id", name="uq_campaign_asset"),
    )


class CampaignWorkflow(Base):
    __tablename__ = "campaign_workflows"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("campaigns.id", ondelete="CASCADE")
    )
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_templates.id", ondelete="CASCADE")
    )

    campaign = relationship("Campaign")
    workflow = relationship("WorkflowTemplate")

    __table_args__ = (
        UniqueConstraint("campaign_id", "workflow_id", name="uq_campaign_workflow"),
    )


class AIJob(Base):
    __tablename__ = "ai_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    brand_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=True
    )
    workflow_template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("workflow_templates.id", ondelete="CASCADE"), nullable=True
    )
    asset_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(50), default="pending")
    job_type: Mapped[str] = mapped_column(String(100), default="generation")
    
    inputs: Mapped[dict] = mapped_column(JSONB, default=dict)
    outputs: Mapped[dict] = mapped_column(JSONB, default=dict)
    callback_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User")
    brand = relationship("Brand")
    workflow = relationship("WorkflowTemplate")
    asset = relationship("Asset")

class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    workflow_json: Mapped[str] = mapped_column(Text)

class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    prompt_text: Mapped[str] = mapped_column(Text)

class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    image_path: Mapped[str] = mapped_column(String(1000))

    brand = relationship("Brand")

class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(255))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    user = relationship("User")

# --- Production Ready Database Session Management ---
# Create async database engine with optimized connection pooling parameters for scaling
engine = create_async_engine(
    settings.POSTGRES_URL,
    echo=False,
    pool_size=20,            # 20 standard persistent connections
    max_overflow=100,        # Up to 100 extra temporary connections under heavy load spikes
    pool_timeout=30,          # Fail fast if connection queue is blocked
    pool_recycle=1800,        # Cycle connections every 30 minutes to prevent stale DB state
    pool_pre_ping=True        # Pre-verify connection status before executing queries
)

# Create session maker
async_session_maker = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# FastAPI Dependency for obtaining Database Session
async def get_db():
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()
