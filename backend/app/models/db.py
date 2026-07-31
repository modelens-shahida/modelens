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
    last_low_credit_warning_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    notify_on_job_complete: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_on_training_complete: Mapped[bool] = mapped_column(Boolean, default=True)

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
    tier: Mapped[str] = mapped_column(String(50), default="free", index=True)
    domain_whitelist: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True, default=None)
    monthly_credit_quota: Mapped[int] = mapped_column(Integer, default=100)
    credits_used_this_month: Mapped[int] = mapped_column(Integer, default=0)
    tier_reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)

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
        Index("idx_brand_members_user_id", "user_id"),
    )

class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    filename: Mapped[str] = mapped_column(String(500))
    storage_path: Mapped[str] = mapped_column(String(1000))
    asset_type: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), server_default=func.now(), nullable=False)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    aspect_ratio: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    preview_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    meta: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    brand = relationship("Brand")
    tags = relationship("AssetTag", back_populates="asset", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        Index("idx_assets_brand_id", "brand_id"),
        Index("idx_assets_metadata_gin", "metadata", postgresql_using="gin"),
        Index("idx_assets_deleted_at", "deleted_at"),
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
    theme_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campaign_themes.id", ondelete="SET NULL"), nullable=True
    )

    brand = relationship("Brand")
    theme = relationship("CampaignTheme")


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

    __table_args__ = (
        Index("idx_ai_jobs_brand_id", "brand_id"),
        Index("idx_ai_jobs_user_id", "user_id"),
    )

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

    __table_args__ = (
        Index("idx_characters_brand_id", "brand_id"),
    )

class CampaignTheme(Base):
    __tablename__ = "campaign_themes"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    theme_json: Mapped[dict] = mapped_column(JSONB, default=dict)

    brand = relationship("Brand")

    __table_args__ = (
        Index("idx_campaign_themes_brand_id", "brand_id"),
    )

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



# ========================== New Models (Schema v1 Upgrade) =========

class CharacterVersion(Base):
    __tablename__ = "character_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    prompt_trigger: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_image_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    validation_image_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    config_overrides: Mapped[dict] = mapped_column(JSONB, default=dict)
    mlflow_run_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    character = relationship("Character")


class CharacterEmbedding(Base):
    __tablename__ = "character_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[int] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), index=True
    )
    version_id: Mapped[int] = mapped_column(
        ForeignKey("character_versions.id", ondelete="CASCADE"), index=True
    )
    embedding: Mapped[Optional[list]] = mapped_column(Vector(1536), nullable=True)
    tag: Mapped[str] = mapped_column(String(255))

    character = relationship("Character")
    version = relationship("CharacterVersion")


class ThemePackage(Base):
    __tablename__ = "theme_packages"

    id: Mapped[int] = mapped_column(primary_key=True)
    theme_id: Mapped[int] = mapped_column(
        ForeignKey("campaign_themes.id", ondelete="CASCADE"), index=True
    )
    character_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("characters.id", ondelete="SET NULL"), nullable=True
    )
    workflow_template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("workflow_templates.id", ondelete="SET NULL"), nullable=True
    )
    prompt_template_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("prompt_templates.id", ondelete="SET NULL"), nullable=True
    )
    location_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    theme = relationship("CampaignTheme")
    character = relationship("Character")
    workflow_template = relationship("WorkflowTemplate")
    prompt_template = relationship("PromptTemplate")


class GeneratedVideo(Base):
    __tablename__ = "generated_videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("ai_jobs.id", ondelete="CASCADE"), index=True
    )
    source_asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(500))
    storage_path: Mapped[str] = mapped_column(String(1000))
    motion_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job = relationship("AIJob")
    source_asset = relationship("Asset")


class FixRequest(Base):
    __tablename__ = "fix_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ai_jobs.id", ondelete="SET NULL"), nullable=True
    )
    updated_asset_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )
    requester_notes: Mapped[str] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(50), default="pending")
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    original_asset = relationship("Asset", foreign_keys=[original_asset_id])
    updated_asset = relationship("Asset", foreign_keys=[updated_asset_id])


class WebhookSubscription(Base):
    __tablename__ = "webhook_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(1000))
    events: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    secret_token: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, default=None)
    filter_rules: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=None)
    payload_format: Mapped[str] = mapped_column(String(50), default="verbose")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    brand = relationship("Brand")



class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    brand_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), index=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    client_ip: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    brand = relationship("Brand")



class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[int] = mapped_column(Integer)
    transaction_type: Mapped[str] = mapped_column(String(50), index=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    balance_after: Mapped[int] = mapped_column(Integer)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")



class WebhookLog(Base):
    __tablename__ = "webhook_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("webhook_subscriptions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    is_success: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    subscription = relationship("WebhookSubscription")



class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(100), index=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")



class WebhookDeliveryLog(Base):
    __tablename__ = "webhook_delivery_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("webhook_subscriptions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    response_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    response_body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="success", index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    subscription = relationship("WebhookSubscription")



class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    role: Mapped[str] = mapped_column(String(50))
    brand_id: Mapped[int] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, default=None)

    brand = relationship("Brand")



class CampaignTemplate(Base):
    __tablename__ = "campaign_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EditorialAsset(Base):
    __tablename__ = "editorial_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(
        ForeignKey("assets.id", ondelete="CASCADE"), unique=True, index=True
    )
    shot_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    camera_body: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    lens_spec: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    lighting_setup: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    composition_grid: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    style_mood: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    asset = relationship("Asset")



class VideoProject(Base):
    __tablename__ = "video_projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    master_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    aspect_ratio: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="16:9")
    mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="standard")
    status: Mapped[str] = mapped_column(String(50), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    clips = relationship("VideoClip", back_populates="project", cascade="all, delete-orphan")
    renders = relationship("VideoRender", back_populates="project", cascade="all, delete-orphan")


class VideoClip(Base):
    __tablename__ = "video_clips"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(default=0)
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    motion_preset: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    duration: Mapped[Optional[float]] = mapped_column(nullable=True, default=4.0)
    start_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    end_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provider_job_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    clip_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    credits_consumed: Mapped[int] = mapped_column(default=0)
    trim_start: Mapped[Optional[float]] = mapped_column(nullable=True)
    trim_end: Mapped[Optional[float]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project = relationship("VideoProject", back_populates="clips")


class VideoRender(Base):
    __tablename__ = "video_renders"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("video_projects.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    output_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="1080p")
    audio_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    project = relationship("VideoProject", back_populates="renders")


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
