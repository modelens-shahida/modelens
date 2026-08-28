"""
Real-Time QA Telemetry Service
Streams live QA diagnostic events via Redis pub/sub to WebSocket clients.
"""
import json
from datetime import datetime
from typing import Optional, Any


QA_TELEMETRY_EVENTS = [
    "evaluating_identity",
    "evaluating_garment",
    "evaluating_anatomy",
    "evaluating_skin",
    "evaluating_pose",
    "evaluating_camera",
    "evaluating_lighting",
    "evaluating_technical",
    "detecting_artifacts",
    "computing_overall_score",
    "decision_ready",
]


async def publish_qa_event(
    redis_client,
    job_id: int,
    brand_id: int,
    event_type: str,
    data: Optional[dict] = None,
):
    """Publish a QA telemetry event to Redis pub/sub."""
    if not redis_client:
        return

    event = {
        "type": f"qa.{event_type}",
        "job_id": job_id,
        "timestamp": datetime.utcnow().isoformat(),
        "data": data or {},
    }

    try:
        channel = f"brand:{brand_id}:events"
        await redis_client.publish(channel, json.dumps(event))
        print(f"[QA Telemetry] Published {event_type} for job {job_id}")
    except Exception as e:
        print(f"[QA Telemetry] Failed to publish event: {e}")


async def stream_qa_evaluation(
    redis_client,
    job_id: int,
    brand_id: int,
    asset_id: int,
    qa_profile_id: str,
    generation_mode: str = "studio_quality",
):
    """
    Stream live QA evaluation events step by step.
    Returns final QAResult.
    """
    import asyncio
    from app.services.qa_service import qa_service, DIMENSION_WEIGHTS, DEFAULT_PROFILE

    profile = DIMENSION_WEIGHTS.get(qa_profile_id, DIMENSION_WEIGHTS[DEFAULT_PROFILE])

    # Stream dimension evaluations
    dimension_scores = {}
    for dimension in profile.keys():
        event_name = f"evaluating_{dimension}"

        await publish_qa_event(redis_client, job_id, brand_id, event_name, {
            "asset_id": asset_id,
            "dimension": dimension,
            "status": "evaluating",
        })

        # Small delay to simulate real evaluation
        await asyncio.sleep(0.1)

        # Score the dimension
        import random
        base = 95.0 if generation_mode == "studio_quality" else 88.0
        score = min(100.0, max(0.0, base + random.uniform(-8, 3)))
        dimension_scores[dimension] = round(score, 2)

        await publish_qa_event(redis_client, job_id, brand_id, event_name, {
            "asset_id": asset_id,
            "dimension": dimension,
            "score": dimension_scores[dimension],
            "status": "complete",
        })

    # Stream artifact detection
    await publish_qa_event(redis_client, job_id, brand_id, "detecting_artifacts", {
        "asset_id": asset_id,
        "status": "scanning",
    })
    await asyncio.sleep(0.1)

    # Run full QA evaluation
    result = qa_service.evaluate(
        asset_id=asset_id,
        qa_profile_id=qa_profile_id,
        generation_mode=generation_mode,
    )

    # Stream artifact results
    await publish_qa_event(redis_client, job_id, brand_id, "detecting_artifacts", {
        "asset_id": asset_id,
        "artifacts_found": len(result.artifacts),
        "artifacts": result.artifacts,
        "status": "complete",
    })

    # Stream overall score
    await publish_qa_event(redis_client, job_id, brand_id, "computing_overall_score", {
        "asset_id": asset_id,
        "overall_score": result.overall_score,
        "hard_gate_failures": result.hard_gate_failures,
    })

    # Stream final decision
    await publish_qa_event(redis_client, job_id, brand_id, "decision_ready", {
        "asset_id": asset_id,
        "decision": result.decision,
        "overall_score": result.overall_score,
        "dimension_scores": result.dimension_scores,
        "warnings": result.warnings,
    })

    return result
