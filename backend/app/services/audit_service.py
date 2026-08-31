"""
Enterprise Audit Logging Service
Immutable logging of all governed actions across Mode Lens platform.
Section 20 — Mode Lens Production Vocabulary & Taxonomy Registry v1.0
"""
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from enum import Enum


# ========================== Audit Event Types ===================

class AuditEventType(str, Enum):
    # Generation events
    GENERATION_SUBMITTED = "generation.submitted"
    GENERATION_COMPLETED = "generation.completed"
    GENERATION_FAILED = "generation.failed"
    GENERATION_CANCELLED = "generation.cancelled"

    # QA events
    QA_EVALUATED = "qa.evaluated"
    QA_HARD_GATE_OVERRIDE = "qa.hard_gate_override"
    QA_REVIEWED = "qa.reviewed"

    # Touch-up events
    TOUCHUP_DISPATCHED = "touchup.dispatched"
    TOUCHUP_COMPLETED = "touchup.completed"

    # C2PA events
    C2PA_GENERATED = "c2pa.generated"
    C2PA_VERIFIED = "c2pa.verified"

    # Asset events
    ASSET_UPLOADED = "asset.uploaded"
    ASSET_DELETED = "asset.deleted"
    ASSET_APPROVED = "asset.approved"
    ASSET_REJECTED = "asset.rejected"

    # Character events
    CHARACTER_CREATED = "character.created"
    CHARACTER_APPROVED = "character.approved"
    CHARACTER_PROMOTED = "character.promoted"

    # Auth events
    USER_LOGIN = "auth.login"
    USER_LOGOUT = "auth.logout"
    USER_INVITED = "auth.user_invited"
    ROLE_CHANGED = "auth.role_changed"

    # Billing events
    CREDITS_DEDUCTED = "billing.credits_deducted"
    CREDITS_REFUNDED = "billing.credits_refunded"

    # Dataset events
    DATASET_ASSET_ADDED = "dataset.asset_added"
    DATASET_FROZEN = "dataset.frozen"

    # Admin events
    TAXONOMY_APPROVED = "taxonomy.approved"
    TAXONOMY_REJECTED = "taxonomy.rejected"
    SETTINGS_CHANGED = "admin.settings_changed"


# ========================== Audit Service =======================

class AuditService:
    """
    Records immutable audit events for all governed platform actions.
    """

    async def log(
        self,
        db,
        event_type: AuditEventType,
        actor_user_id: int,
        actor_email: str,
        brand_id: Optional[int] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        severity: str = "INFO",
    ):
        """Log an immutable audit event."""
        try:
            from app.models.db import AuditLog

            log = AuditLog(
                event_type=event_type.value,
                actor_user_id=actor_user_id,
                actor_email=actor_email,
                brand_id=brand_id,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata=metadata or {},
                ip_address=ip_address,
                severity=severity,
                created_at=datetime.now(timezone.utc),
            )
            db.add(log)
            await db.flush()
            print(f"[Audit] {event_type.value} by {actor_email}")
        except Exception as e:
            print(f"[Audit] Failed to log event: {e}")

    async def log_generation(
        self,
        db,
        user_id: int,
        user_email: str,
        brand_id: int,
        job_type: str,
        job_id: int,
        credits_used: int,
        generation_mode: str,
        ip_address: Optional[str] = None,
    ):
        """Log generation submission."""
        await self.log(
            db=db,
            event_type=AuditEventType.GENERATION_SUBMITTED,
            actor_user_id=user_id,
            actor_email=user_email,
            brand_id=brand_id,
            resource_type=job_type,
            resource_id=job_id,
            metadata={
                "credits_used": credits_used,
                "generation_mode": generation_mode,
                "job_type": job_type,
            },
            ip_address=ip_address,
        )

    async def log_qa_override(
        self,
        db,
        user_id: int,
        user_email: str,
        brand_id: int,
        evaluation_id: int,
        previous_decision: str,
        new_decision: str,
        notes: Optional[str] = None,
        ip_address: Optional[str] = None,
    ):
        """Log QA hard gate override — high severity."""
        await self.log(
            db=db,
            event_type=AuditEventType.QA_HARD_GATE_OVERRIDE,
            actor_user_id=user_id,
            actor_email=user_email,
            brand_id=brand_id,
            resource_type="qa_evaluation",
            resource_id=evaluation_id,
            metadata={
                "previous_decision": previous_decision,
                "new_decision": new_decision,
                "reviewer_notes": notes,
            },
            ip_address=ip_address,
            severity="HIGH",
        )

    async def log_c2pa(
        self,
        db,
        user_id: int,
        user_email: str,
        brand_id: int,
        asset_id: int,
        manifest_id: str,
        ip_address: Optional[str] = None,
    ):
        """Log C2PA manifest generation."""
        await self.log(
            db=db,
            event_type=AuditEventType.C2PA_GENERATED,
            actor_user_id=user_id,
            actor_email=user_email,
            brand_id=brand_id,
            resource_type="asset",
            resource_id=asset_id,
            metadata={"manifest_id": manifest_id},
            ip_address=ip_address,
        )


# Singleton
audit_service = AuditService()
