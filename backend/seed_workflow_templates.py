import asyncio
import os
import json
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.db import WorkflowTemplate
from app.config import settings

async def seed():
    # Use environment URL or default settings URL
    postgres_url = os.getenv("POSTGRES_URL") or settings.POSTGRES_URL
    # Ensure pg+asyncpg is used
    if postgres_url.startswith("postgresql://"):
        postgres_url = postgres_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(postgres_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # Check if templates already exist
        from sqlalchemy import select
        res = await session.execute(select(WorkflowTemplate))
        existing = res.scalars().all()
        if existing:
            print(f"Templates already exist in database ({len(existing)}). Skipping seed.")
            return

        templates = [
            WorkflowTemplate(
                name="Standard Campaign Workflow",
                description="A template for testing campaign workflows.",
                workflow_json=json.dumps({"steps": ["validate", "approve", "publish"]})
            ),
            WorkflowTemplate(
                name="On-Model Studio Hoodies",
                description="Generates premium catalog shots for outdoor apparel.",
                workflow_json=json.dumps({"nodes": [], "edges": []})
            ),
            WorkflowTemplate(
                name="Flat-Lay Creative Background",
                description="Transforms simple clothing flat-lays into creative lifestyle photos.",
                workflow_json=json.dumps({"steps": ["detect_clothing", "background_generation", "color_grading"]})
            )
        ]

        for t in templates:
            session.add(t)
        await session.commit()
        print("Successfully seeded 3 default workflow templates!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed())
