from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from app.models.db import Asset, AssetTag
from app.services.pipeline import get_embedding


async def full_text_search(
    db: AsyncSession,
    query: str,
    brand_id: int,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """
    PostgreSQL Full-Text Search across asset name, filename, and tags.
    """
    if db.bind.dialect.name == "sqlite":
        # SQLite fallback: simple ILIKE logic mapped via SQLAlchemy select
        like_query = f"%{query}%"
        stmt = (
            select(Asset)
            .outerjoin(AssetTag, AssetTag.asset_id == Asset.id)
            .where(
                Asset.brand_id == brand_id,
                (Asset.name.ilike(like_query)) |
                (Asset.filename.ilike(like_query)) |
                (AssetTag.tag.ilike(like_query))
            )
        )
        result = await db.execute(stmt)
        assets = result.scalars().unique().all()
        
        results = []
        for a in assets:
            score = 1.0 if query.lower() in (a.name or "").lower() else 0.5
            results.append({
                "id": a.id,
                "name": a.name,
                "filename": a.filename,
                "storage_path": a.storage_path,
                "asset_type": a.asset_type,
                "metadata": a.meta,
                "score": score,
                "search_type": "fts",
            })
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[offset : offset + limit]

    fts_query = text("""
        SELECT DISTINCT
            a.id,
            a.name,
            a.filename,
            a.storage_path,
            a.asset_type,
            a.metadata,
            ts_rank(
                to_tsvector('english', coalesce(a.name, '') || ' ' || coalesce(a.filename, '') || ' ' || coalesce(a.metadata::text, '')),
                plainto_tsquery('english', :query)
            ) AS score
        FROM assets a
        LEFT JOIN asset_tags at ON at.asset_id = a.id
        WHERE
            a.brand_id = :brand_id
            AND (
                to_tsvector('english', coalesce(a.name, '') || ' ' || coalesce(a.filename, '') || ' ' || coalesce(a.metadata::text, ''))
                @@ plainto_tsquery('english', :query)
                OR at.tag ILIKE :like_query
            )
        ORDER BY score DESC
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(fts_query, {
        "query": query,
        "brand_id": brand_id,
        "like_query": f"%{query}%",
        "limit": limit,
        "offset": offset,
    })
    rows = result.mappings().all()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "filename": row["filename"],
            "storage_path": row["storage_path"],
            "asset_type": row["asset_type"],
            "metadata": row["metadata"],
            "score": float(row["score"]) if row["score"] else 0.0,
            "search_type": "fts",
        }
        for row in rows
    ]


async def vector_search(
    db: AsyncSession,
    query: str,
    brand_id: int,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """
    Semantic vector search using pgvector cosine distance on asset_tags.embedding.
    """
    if db.bind.dialect.name == "sqlite":
        # SQLite fallback: fetch assets for this brand
        stmt = (
            select(Asset)
            .outerjoin(AssetTag, AssetTag.asset_id == Asset.id)
            .where(
                Asset.brand_id == brand_id
            )
        )
        result = await db.execute(stmt)
        assets = result.scalars().unique().all()
        
        results = []
        for a in assets:
            results.append({
                "id": a.id,
                "name": a.name,
                "filename": a.filename,
                "storage_path": a.storage_path,
                "asset_type": a.asset_type,
                "metadata": a.meta,
                "score": 0.8,
                "search_type": "vector",
            })
        return results[offset : offset + limit]

    embedding = await get_embedding(query)
    embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"

    vector_query = text("""
        SELECT DISTINCT
            a.id,
            a.name,
            a.filename,
            a.storage_path,
            a.asset_type,
            a.metadata,
            MIN(at.embedding <=> CAST(:embedding AS vector)) AS distance
        FROM assets a
        JOIN asset_tags at ON at.asset_id = a.id
        WHERE
            a.brand_id = :brand_id
            AND at.embedding IS NOT NULL
        GROUP BY a.id, a.name, a.filename, a.storage_path, a.asset_type, a.metadata
        ORDER BY distance ASC
        LIMIT :limit OFFSET :offset
    """)

    result = await db.execute(vector_query, {
        "embedding": embedding_str,
        "brand_id": brand_id,
        "limit": limit,
        "offset": offset,
    })
    rows = result.mappings().all()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "filename": row["filename"],
            "storage_path": row["storage_path"],
            "asset_type": row["asset_type"],
            "metadata": row["metadata"],
            "score": 1.0 - float(row["distance"]) if row["distance"] is not None else 0.0,
            "search_type": "vector",
        }
        for row in rows
    ]


def _rrf_score(rank: int, k: int = 60) -> float:
    """Reciprocal Rank Fusion score."""
    return 1.0 / (k + rank)


async def hybrid_search(
    db: AsyncSession,
    query: str,
    brand_id: int,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """
    Hybrid search combining FTS and Vector search via Reciprocal Rank Fusion (RRF).
    """
    fts_results = await full_text_search(db, query, brand_id, limit=limit * 2)
    vector_results = await vector_search(db, query, brand_id, limit=limit * 2)

    scores: dict[int, float] = {}
    asset_map: dict[int, dict] = {}

    for rank, asset in enumerate(fts_results):
        aid = asset["id"]
        scores[aid] = scores.get(aid, 0.0) + _rrf_score(rank)
        asset_map[aid] = asset

    for rank, asset in enumerate(vector_results):
        aid = asset["id"]
        scores[aid] = scores.get(aid, 0.0) + _rrf_score(rank)
        if aid not in asset_map:
            asset_map[aid] = asset

    sorted_ids = sorted(scores.keys(), key=lambda aid: scores[aid], reverse=True)
    paginated = sorted_ids[offset: offset + limit]

    return [
        {**asset_map[aid], "score": scores[aid], "search_type": "hybrid"}
        for aid in paginated
    ]
