"""
C2PA Content Credentials & Cryptographic Provenance Service
Embeds machine-readable C2PA metadata into generated PNG/WebP deliverables.
Section 20 — Mode Lens Production Vocabulary & Taxonomy Registry v1.0
"""
import json
import hashlib
import hmac
import base64
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List


# ========================== C2PA Constants =======================

MODELENS_GENERATOR = "ModeLens/1.0"
MODELENS_CERT_ISSUER = "ModeLens Production CA"
C2PA_SPEC_VERSION = "2.1"


# ========================== Assertion Builders ==================

def build_c2pa_actions(
    workflow_id: str,
    is_touchup: bool = False,
) -> dict:
    """Build c2pa.actions assertion."""
    actions = [
        {
            "action": "c2pa.created",
            "softwareAgent": MODELENS_GENERATOR,
            "when": datetime.now(timezone.utc).isoformat(),
            "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
            "parameters": {
                "workflow_id": workflow_id,
            }
        }
    ]

    if is_touchup:
        actions.append({
            "action": "c2pa.edited",
            "softwareAgent": MODELENS_GENERATOR,
            "when": datetime.now(timezone.utc).isoformat(),
            "parameters": {
                "workflow_id": "WF-TOUCHUP-001",
                "description": "Localized inpainting correction",
            }
        })

    return {"actions": actions}


def build_character_assertion(
    character_id: str,
    character_name: str,
    character_version: str = "1.0",
    reference_set_id: Optional[str] = None,
) -> dict:
    """Build modelens.character assertion."""
    return {
        "character_id": character_id,
        "character_name": character_name,
        "character_version": character_version,
        "character_origin": "CHAR-ORIGIN-SYNTHETIC",
        "reference_set_id": reference_set_id,
        "golden_character": True,
    }


def build_governance_assertion(
    workspace_id: str,
    rights_attestation: bool = True,
    training_permission: str = "DENIED",
    approval_status: str = "APPROVED",
) -> dict:
    """Build modelens.governance assertion (Section 20)."""
    return {
        "workspace_tenant_id": workspace_id,
        "rights_attestation": {
            "status": "ACTIVE" if rights_attestation else "UNVERIFIED",
            "attested_at": datetime.now(timezone.utc).isoformat(),
            "attestation_version": "1.0",
        },
        "training_permission": training_permission,
        "non_training_clause": training_permission == "DENIED",
        "approval_status": approval_status,
        "governance_version": "Section-20-v1.0",
    }


def build_qa_assertion(
    overall_score: float,
    decision: str,
    qa_profile_id: str,
    dimension_scores: Optional[Dict] = None,
) -> dict:
    """Build modelens.qa assertion."""
    return {
        "qa_profile_id": qa_profile_id,
        "overall_score": overall_score,
        "decision": decision,
        "compliance_pass": decision in ("QA-PASS", "QA-PASS-WARNING"),
        "dimension_scores": dimension_scores or {},
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_creative_work_assertion(
    brand_id: int,
    brand_name: str,
    created_at: Optional[str] = None,
) -> dict:
    """Build stds.schema-org.CreativeWork assertion."""
    return {
        "@context": "https://schema.org",
        "@type": "CreativeWork",
        "generator": MODELENS_GENERATOR,
        "dateCreated": created_at or datetime.now(timezone.utc).isoformat(),
        "producer": {
            "@type": "Organization",
            "name": brand_name,
            "identifier": str(brand_id),
        },
        "license": "https://modelens.ai/terms/generated-content",
        "acquireLicensePage": "https://modelens.ai/licensing",
    }


# ========================== Manifest Builder ====================

class C2PAService:
    """
    Builds, signs, and embeds C2PA manifests into generated assets.
    """

    def __init__(self, signing_secret: str = "modelens-c2pa-secret"):
        self.signing_secret = signing_secret

    def build_manifest(
        self,
        asset_id: int,
        workflow_id: str,
        brand_id: int,
        brand_name: str,
        workspace_id: str,
        character_id: Optional[str] = None,
        character_name: Optional[str] = None,
        reference_set_id: Optional[str] = None,
        qa_score: Optional[float] = None,
        qa_decision: Optional[str] = None,
        qa_profile_id: Optional[str] = None,
        dimension_scores: Optional[Dict] = None,
        rights_attestation: bool = True,
        training_permission: str = "DENIED",
        is_touchup: bool = False,
    ) -> dict:
        """Build complete C2PA manifest with all assertions."""

        assertions = []

        # c2pa.actions
        assertions.append({
            "label": "c2pa.actions",
            "data": build_c2pa_actions(workflow_id, is_touchup),
        })

        # modelens.character (if character used)
        if character_id:
            assertions.append({
                "label": "modelens.character",
                "data": build_character_assertion(
                    character_id=character_id,
                    character_name=character_name or "",
                    reference_set_id=reference_set_id,
                ),
            })

        # modelens.governance
        assertions.append({
            "label": "modelens.governance",
            "data": build_governance_assertion(
                workspace_id=workspace_id,
                rights_attestation=rights_attestation,
                training_permission=training_permission,
            ),
        })

        # modelens.qa
        if qa_score is not None:
            assertions.append({
                "label": "modelens.qa",
                "data": build_qa_assertion(
                    overall_score=qa_score,
                    decision=qa_decision or "QA-PASS",
                    qa_profile_id=qa_profile_id or "QA-PROFILE-CATALOG-001",
                    dimension_scores=dimension_scores,
                ),
            })

        # stds.schema-org.CreativeWork
        assertions.append({
            "label": "stds.schema-org.CreativeWork",
            "data": build_creative_work_assertion(
                brand_id=brand_id,
                brand_name=brand_name,
            ),
        })

        manifest = {
            "c2pa_version": C2PA_SPEC_VERSION,
            "manifest_id": f"modelens:asset:{asset_id}:{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "generator": MODELENS_GENERATOR,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "asset_id": asset_id,
            "assertions": assertions,
            "claim_generator": MODELENS_GENERATOR,
        }

        # Sign the manifest
        manifest["signature"] = self._sign_manifest(manifest)
        manifest["cert_issuer"] = MODELENS_CERT_ISSUER

        return manifest

    def _sign_manifest(self, manifest: dict) -> str:
        """Generate HMAC-SHA256 signature for manifest."""
        payload = json.dumps({
            k: v for k, v in manifest.items()
            if k not in ("signature", "cert_issuer")
        }, sort_keys=True)

        sig = hmac.new(
            self.signing_secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        return f"sha256={sig}"

    def verify_manifest(self, manifest: dict) -> Dict[str, Any]:
        """Verify C2PA manifest signature and return parsed assertions."""
        provided_sig = manifest.get("signature", "")

        expected_sig = self._sign_manifest({
            k: v for k, v in manifest.items()
            if k not in ("signature", "cert_issuer")
        })

        is_valid = hmac.compare_digest(
            provided_sig.encode(),
            expected_sig.encode(),
        )

        return {
            "valid": is_valid,
            "tamper_detected": not is_valid,
            "manifest_id": manifest.get("manifest_id"),
            "generator": manifest.get("generator"),
            "created_at": manifest.get("created_at"),
            "cert_issuer": manifest.get("cert_issuer"),
            "assertions": manifest.get("assertions", []),
            "asset_id": manifest.get("asset_id"),
        }

    def embed_in_metadata(self, manifest: dict) -> str:
        """Encode C2PA manifest as base64 for embedding in image metadata."""
        return base64.b64encode(
            json.dumps(manifest).encode()
        ).decode()

    def extract_from_metadata(self, encoded: str) -> dict:
        """Decode C2PA manifest from image metadata."""
        return json.loads(base64.b64decode(encoded).decode())


# Singleton
c2pa_service = C2PAService()
