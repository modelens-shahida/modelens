"""
Multi-Dimensional QA & Automated Scoring Service
Section 21 — Mode Lens Production Vocabulary & Taxonomy Registry v1.0
"""
import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


# ========================== QA Dimensions ========================

DIMENSION_WEIGHTS = {
    "QA-PROFILE-CATALOG-001": {
        "garment":   {"weight": 0.30, "hard_gate": 94.0},
        "identity":  {"weight": 0.20, "hard_gate": 94.0},
        "anatomy":   {"weight": 0.15, "hard_gate": 90.0},
        "pose":      {"weight": 0.10, "hard_gate": None},
        "skin":      {"weight": 0.07, "hard_gate": None},
        "camera":    {"weight": 0.05, "hard_gate": None},
        "lighting":  {"weight": 0.05, "hard_gate": None},
        "environment": {"weight": 0.03, "hard_gate": None},
        "technical": {"weight": 0.05, "hard_gate": 95.0},
    },
    "QA-PROFILE-GHOST-001": {
        "garment":   {"weight": 0.40, "hard_gate": 92.0},
        "anatomy":   {"weight": 0.20, "hard_gate": 88.0},
        "technical": {"weight": 0.20, "hard_gate": 95.0},
        "skin":      {"weight": 0.10, "hard_gate": None},
        "lighting":  {"weight": 0.10, "hard_gate": None},
    },
    "QA-PROFILE-SKETCH-001": {
        "garment":   {"weight": 0.35, "hard_gate": 90.0},
        "identity":  {"weight": 0.25, "hard_gate": 90.0},
        "anatomy":   {"weight": 0.20, "hard_gate": 85.0},
        "technical": {"weight": 0.20, "hard_gate": 95.0},
    },
}

DEFAULT_PROFILE = "QA-PROFILE-CATALOG-001"

# QA Decision thresholds
QA_PASS_THRESHOLD = 92.0
QA_PASS_WARNING_THRESHOLD = 85.0
QA_AUTO_CORRECT_THRESHOLD = 75.0
QA_HUMAN_REVIEW_THRESHOLD = 65.0

# Known artifact codes
ARTIFACT_CODES = [
    "ART-HAND-001",    # Extra/missing fingers
    "ART-HAND-002",    # Distorted hand geometry
    "ART-FACE-001",    # Identity drift
    "ART-FACE-002",    # Age inconsistency
    "ART-GAR-001",     # Color shift
    "ART-GAR-002",     # Print distortion
    "ART-GAR-003",     # Missing seam
    "ART-SKIN-001",    # Plastic skin texture
    "ART-SKIN-002",    # Tone inconsistency
    "ART-ANATOMY-001", # Proportional drift
    "ART-BG-001",      # Background bleed
]


@dataclass
class QADimensionResult:
    dimension: str
    score: float
    hard_gate: Optional[float]
    passed_gate: bool
    notes: str = ""


@dataclass
class QAResult:
    overall_score: float
    decision: str
    dimension_scores: Dict[str, float]
    hard_gate_failures: List[str]
    artifacts: List[Dict[str, Any]]
    warnings: List[str]


class QAService:
    """
    Multi-dimensional QA scoring engine.
    Evaluates generation outputs against QA profiles.
    """

    def evaluate(
        self,
        asset_id: int,
        qa_profile_id: str,
        workflow_id: Optional[str] = None,
        reference_asset_ids: Optional[List[int]] = None,
        generation_mode: str = "studio_quality",
    ) -> QAResult:
        """
        Evaluate an asset against a QA profile.
        Returns QAResult with scores, decision, and artifacts.
        """
        profile = DIMENSION_WEIGHTS.get(qa_profile_id, DIMENSION_WEIGHTS[DEFAULT_PROFILE])

        # Generate dimension scores (mock scoring — replace with real CV models)
        dimension_scores = self._score_dimensions(profile, generation_mode)

        # Check hard gates
        hard_gate_failures = []
        for dim, config in profile.items():
            if config["hard_gate"] is not None:
                score = dimension_scores.get(dim, 0)
                if score < config["hard_gate"]:
                    hard_gate_failures.append(f"{dim.upper()}_GATE_FAIL ({score:.1f} < {config['hard_gate']})")

        # Calculate weighted overall score
        overall_score = sum(
            dimension_scores.get(dim, 0) * config["weight"]
            for dim, config in profile.items()
        )

        # Detect artifacts
        artifacts = self._detect_artifacts(dimension_scores, generation_mode)

        # Determine decision state
        decision = self._determine_decision(
            overall_score,
            hard_gate_failures,
            artifacts,
            generation_mode,
        )

        # Build warnings
        warnings = []
        if overall_score < QA_PASS_THRESHOLD and not hard_gate_failures:
            warnings.append(f"Overall score {overall_score:.1f} below pass threshold {QA_PASS_THRESHOLD}")
        if artifacts:
            warnings.append(f"{len(artifacts)} artifact(s) detected")

        return QAResult(
            overall_score=round(overall_score, 2),
            decision=decision,
            dimension_scores={k: round(v, 2) for k, v in dimension_scores.items()},
            hard_gate_failures=hard_gate_failures,
            artifacts=artifacts,
            warnings=warnings,
        )

    def _score_dimensions(
        self,
        profile: Dict,
        generation_mode: str,
    ) -> Dict[str, float]:
        """
        Score each QA dimension.
        In production, replace with real CV model calls.
        """
        base_quality = 95.0 if generation_mode == "studio_quality" else 88.0
        scores = {}

        for dim in profile.keys():
            # Simulate dimension scores with slight variance
            variance = random.uniform(-8, 3)
            score = min(100.0, max(0.0, base_quality + variance))
            scores[dim] = score

        return scores

    def _detect_artifacts(
        self,
        dimension_scores: Dict[str, float],
        generation_mode: str,
    ) -> List[Dict[str, Any]]:
        """Detect localized defect artifacts with bounding boxes."""
        artifacts = []

        # Check for hand artifacts (common in AI generation)
        if dimension_scores.get("anatomy", 100) < 85:
            artifacts.append({
                "artifact_code": "ART-HAND-001",
                "severity": "WARNING",
                "bbox_x": 0.45,
                "bbox_y": 0.70,
                "bbox_width": 0.15,
                "bbox_height": 0.12,
                "description": "Potential finger geometry issue detected",
            })

        # Check for garment artifacts
        if dimension_scores.get("garment", 100) < 90:
            artifacts.append({
                "artifact_code": "ART-GAR-002",
                "severity": "WARNING",
                "bbox_x": 0.25,
                "bbox_y": 0.40,
                "bbox_width": 0.50,
                "bbox_height": 0.30,
                "description": "Garment print or texture inconsistency detected",
            })

        # Check for identity artifacts
        if dimension_scores.get("identity", 100) < 90:
            artifacts.append({
                "artifact_code": "ART-FACE-001",
                "severity": "BLOCK",
                "bbox_x": 0.30,
                "bbox_y": 0.05,
                "bbox_width": 0.40,
                "bbox_height": 0.30,
                "description": "Facial identity drift detected",
            })

        return artifacts

    def _determine_decision(
        self,
        overall_score: float,
        hard_gate_failures: List[str],
        artifacts: List[Dict],
        generation_mode: str,
    ) -> str:
        """Determine QA decision state based on scores and artifacts."""
        # Hard gate failure always fails
        if hard_gate_failures:
            return "QA-FAIL"

        # Check for blocking artifacts
        blocking = [a for a in artifacts if a.get("severity") == "BLOCK"]
        if blocking:
            return "QA-FAIL"

        # Score-based decision
        if overall_score >= QA_PASS_THRESHOLD:
            if artifacts:
                return "QA-PASS-WARNING"
            return "QA-PASS"
        elif overall_score >= QA_AUTO_CORRECT_THRESHOLD:
            if artifacts:
                return "QA-AUTO-CORRECT"
            return "QA-PASS-WARNING"
        elif overall_score >= QA_HUMAN_REVIEW_THRESHOLD:
            return "QA-HUMAN-REVIEW"
        else:
            return "QA-FAIL"


# Singleton
qa_service = QAService()
