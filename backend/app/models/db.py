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
    credits: Mapped[int] = mapped_column(Integer, default=100)
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
    brand_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), nullable=True, index=True
    )
    amount: Mapped[int] = mapped_column(Integer)
    transaction_type: Mapped[str] = mapped_column(String(50), index=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    balance_after: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="completed")
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User")
    brand = relationship("Brand")



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



class GhostJob(Base):
    __tablename__ = "ghost_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    product_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    garment_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    view: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    aspect_ratio: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    resolution: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    preserve_print: Mapped[bool] = mapped_column(default=True)
    preserve_seams: Mapped[bool] = mapped_column(default=True)
    generation_mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    credits_reserved: Mapped[int] = mapped_column(default=0)
    credits_consumed: Mapped[int] = mapped_column(default=0)
    progress: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assets = relationship("GhostJobAsset", back_populates="job", cascade="all, delete-orphan")
    outputs = relationship("GhostOutput", back_populates="job", cascade="all, delete-orphan")


class GhostJobAsset(Base):
    __tablename__ = "ghost_job_assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("ghost_jobs.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    mask_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    crop_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job = relationship("GhostJob", back_populates="assets")


class GhostOutput(Base):
    __tablename__ = "ghost_outputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("ghost_jobs.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    output_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    fidelity_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    api_interaction_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job = relationship("GhostJob", back_populates="outputs")


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


class SketchJob(Base):
    __tablename__ = "sketch_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    product_hint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    material_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_brief: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    background_brief: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="ON_MODEL")
    resolution: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="2K")
    aspect_ratio: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="3:4")
    generation_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="studio_quality")
    credits_reserved: Mapped[int] = mapped_column(default=0)
    credits_consumed: Mapped[int] = mapped_column(default=0)
    progress: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    references = relationship("SketchJobReference", back_populates="job", cascade="all, delete-orphan")
    outputs = relationship("SketchOutput", back_populates="job", cascade="all, delete-orphan")


class SketchJobReference(Base):
    __tablename__ = "sketch_job_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("sketch_jobs.id", ondelete="CASCADE"), index=True)
    reference_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    mask_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job = relationship("SketchJob", back_populates="references")


class SketchOutput(Base):
    __tablename__ = "sketch_outputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("sketch_jobs.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    output_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    api_interaction_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job = relationship("SketchJob", back_populates="outputs")



class CatalogJob(Base):
    __tablename__ = "catalog_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    engine_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="product_to_model")
    generation_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="studio_quality")
    model_identity: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pose: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    background: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    aspect_ratio: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="4:5")
    resolution: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="2K")
    total_items: Mapped[int] = mapped_column(default=0)
    completed_items: Mapped[int] = mapped_column(default=0)
    failed_items: Mapped[int] = mapped_column(default=0)
    credits_reserved: Mapped[int] = mapped_column(default=0)
    credits_consumed: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = relationship("CatalogJobItem", back_populates="job", cascade="all, delete-orphan")


class CatalogJobItem(Base):
    __tablename__ = "catalog_job_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("catalog_jobs.id", ondelete="CASCADE"), index=True)
    sku_tag: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    product_image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    mask_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    output_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    fidelity_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    provider_job_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    job = relationship("CatalogJob", back_populates="items")



class CatalogOutput(Base):
    __tablename__ = "catalog_outputs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("catalog_jobs.id", ondelete="CASCADE"), index=True)
    job_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("catalog_job_items.id", ondelete="SET NULL"), nullable=True)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    output_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    api_interaction_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)



class AngleShot(Base):
    __tablename__ = "angle_shots"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    slug: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    framing: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pose: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    view_direction: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    reference_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    pose_map_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    depth_map_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    segmentation_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    camera_yaw: Mapped[Optional[float]] = mapped_column(nullable=True)
    camera_pitch: Mapped[Optional[float]] = mapped_column(nullable=True)
    camera_roll: Mapped[Optional[float]] = mapped_column(nullable=True)
    camera_distance: Mapped[Optional[float]] = mapped_column(nullable=True)
    focal_length_mm: Mapped[Optional[float]] = mapped_column(nullable=True)
    crop_top: Mapped[Optional[float]] = mapped_column(nullable=True)
    crop_bottom: Mapped[Optional[float]] = mapped_column(nullable=True)
    subject_scale: Mapped[Optional[float]] = mapped_column(nullable=True)
    is_custom: Mapped[bool] = mapped_column(default=False)
    is_premium: Mapped[bool] = mapped_column(default=False)
    is_visible: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    version: Mapped[int] = mapped_column(default=1)
    prompt_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    negative_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generation_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    quality_rules: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    age_groups: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    gender_rules: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    tags: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    compatibilities = relationship("AngleShotCompatibility", back_populates="angle_shot", cascade="all, delete-orphan")
    versions = relationship("AngleShotVersion", back_populates="angle_shot", cascade="all, delete-orphan")


class AngleShotCompatibility(Base):
    __tablename__ = "angle_shot_compatibilities"

    id: Mapped[int] = mapped_column(primary_key=True)
    angle_shot_id: Mapped[int] = mapped_column(ForeignKey("angle_shots.id", ondelete="CASCADE"), index=True)
    product_type: Mapped[str] = mapped_column(String(100))
    compatible: Mapped[bool] = mapped_column(default=True)
    warning_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    angle_shot = relationship("AngleShot", back_populates="compatibilities")


class AngleShotVersion(Base):
    __tablename__ = "angle_shot_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    angle_shot_id: Mapped[int] = mapped_column(ForeignKey("angle_shots.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(default=1)
    configuration: Mapped[dict] = mapped_column(JSONB, default=dict)
    change_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    angle_shot = relationship("AngleShot", back_populates="versions")


class ShootAngleShot(Base):
    __tablename__ = "shoot_angle_shots"

    id: Mapped[int] = mapped_column(primary_key=True)
    shoot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), nullable=True, index=True)
    shoot_product_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    angle_shot_id: Mapped[int] = mapped_column(ForeignKey("angle_shots.id", ondelete="CASCADE"), index=True)
    angle_shot_version: Mapped[int] = mapped_column(default=1)
    configuration: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    position: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(50), default="selected")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BrandModel(Base):
    __tablename__ = "brand_models"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255))
    gender: Mapped[str] = mapped_column(String(50), default="Female")
    full_body_reference_asset_id: Mapped[str] = mapped_column(String(100))
    portrait_reference_asset_id: Mapped[str] = mapped_column(String(100))
    appearance_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rights_confirmed: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("workspace_id", "name", name="uq_brand_model_workspace_name"),
    )


class FluidSession(Base):
    __tablename__ = "fluid_sessions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    workspace_id: Mapped[str] = mapped_column(String(100), index=True)
    name: Mapped[str] = mapped_column(String(255))
    model_id: Mapped[str] = mapped_column(String(100), default="model_01")
    model_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scene_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pose_reference_asset_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    background_asset_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    product_ids: Mapped[list] = mapped_column(JSONB, default=list)
    aspect_ratio: Mapped[str] = mapped_column(String(20), default="4:5")
    resolution: Mapped[str] = mapped_column(String(20), default="2K")
    generation_mode: Mapped[str] = mapped_column(String(50), default="QUALITY")
    active_layer_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    layers = relationship("FluidLayer", back_populates="session", cascade="all, delete-orphan")


class FluidLayer(Base):
    __tablename__ = "fluid_layers"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("fluid_sessions.id", ondelete="CASCADE"), index=True)
    parent_layer_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    operation: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(100))
    provider_model: Mapped[str] = mapped_column(String(100))
    provider_job_id: Mapped[str] = mapped_column(String(100))
    image_url: Mapped[str] = mapped_column(String(1000))
    mask_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    aspect_ratio: Mapped[str] = mapped_column(String(20))
    quality_score: Mapped[float] = mapped_column(default=1.0)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session = relationship("FluidSession", back_populates="layers")



class TaxonomyItem(Base):
    __tablename__ = "taxonomy_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    taxonomy_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    taxonomy_type: Mapped[str] = mapped_column(String(50), index=True)
    family: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="1.0")
    approval_status: Mapped[str] = mapped_column(String(50), default="pending", index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    recommended_for: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    not_recommended_for: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    configuration: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



# ========================== Digital Asset Registry ==============

class AssetVersion(Base):
    __tablename__ = "asset_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(default=1)
    storage_uri: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content_hash_sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    width: Mapped[Optional[int]] = mapped_column(nullable=True)
    height: Mapped[Optional[int]] = mapped_column(nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AssetRelationship(Base):
    __tablename__ = "asset_relationships"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    target_asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    relationship_type: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReferenceSet(Base):
    __tablename__ = "reference_sets"

    id: Mapped[int] = mapped_column(primary_key=True)
    character_id: Mapped[Optional[int]] = mapped_column(ForeignKey("characters.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items = relationship("ReferenceSetItem", back_populates="reference_set", cascade="all, delete-orphan")


class ReferenceSetItem(Base):
    __tablename__ = "reference_set_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference_set_id: Mapped[int] = mapped_column(ForeignKey("reference_sets.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    view_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    position: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reference_set = relationship("ReferenceSet", back_populates="items")


# ========================== QA Registry =========================

class QAProfile(Base):
    __tablename__ = "qa_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    qa_profile_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    workflow: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    generation_mode: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    dimensions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    overall_pass_threshold: Mapped[Optional[float]] = mapped_column(nullable=True, default=92.0)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    evaluations = relationship("QAEvaluation", back_populates="profile", cascade="all, delete-orphan")


class QAEvaluation(Base):
    __tablename__ = "qa_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    qa_profile_id: Mapped[int] = mapped_column(ForeignKey("qa_profiles.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    job_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    job_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    overall_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    decision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    dimension_scores: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    hard_gate_failures: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profile = relationship("QAProfile", back_populates="evaluations")
    artifacts = relationship("QAArtifact", back_populates="evaluation", cascade="all, delete-orphan")


class QAArtifact(Base):
    __tablename__ = "qa_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_id: Mapped[int] = mapped_column(ForeignKey("qa_evaluations.id", ondelete="CASCADE"), index=True)
    artifact_code: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(50), default="WARNING")
    bbox_x: Mapped[Optional[float]] = mapped_column(nullable=True)
    bbox_y: Mapped[Optional[float]] = mapped_column(nullable=True)
    bbox_width: Mapped[Optional[float]] = mapped_column(nullable=True)
    bbox_height: Mapped[Optional[float]] = mapped_column(nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    evaluation = relationship("QAEvaluation", back_populates="artifacts")


# ========================== Workflow Node Map ====================

class WorkflowNodeMap(Base):
    __tablename__ = "workflow_node_maps"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(100), index=True)
    taxonomy_type: Mapped[str] = mapped_column(String(50))
    taxonomy_id: Mapped[str] = mapped_column(String(100))
    node_id: Mapped[str] = mapped_column(String(50))
    field_name: Mapped[str] = mapped_column(String(100))
    value_mapping: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)



class AuditLog(Base):
    __tablename__ = "audit_logs_v2"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    brand_id: Mapped[Optional[int]] = mapped_column(ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True)
    resource_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), default="INFO")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


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
