import asyncio
import os
import csv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.ext.compiler import compiles
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

# Custom compile rules for SQLite
@compiles(Vector, "sqlite")
def compile_vector_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from app.models.db import AngleShot, AngleShotCompatibility, AngleShotVersion, Base
from app.config import settings

# Strip PostgreSQL indexes that use unsupported options or FTS functions if running SQLite
for table in Base.metadata.tables.values():
    for index in list(table.indexes):
        if index.name and ("fts" in index.name or "ops" in index.name or "gist" in index.name or "vector" in index.name):
            table.indexes.remove(index)


# Columns that should be saved inside quality_rules JSONB field
METADATA_KEYS = [
    "version", "tier", "short_label", "body_yaw_deg", "torso_yaw_deg", 
    "face_yaw_deg", "face_pitch_deg", "gaze_target", "weight_distribution", 
    "left_arm", "right_arm", "left_hand", "right_hand", "left_leg", "right_leg", 
    "movement", "camera_height", "camera_roll_deg", "lens_max_mm", 
    "subject_scale_pct", "crop_rule", "hands_visibility", "feet_visibility", 
    "required_source_views", "incompatible_products", "age_groups", 
    "pose_control_mode", "keypoint_strictness", "garment_priority", 
    "fabric_motion", "use_cases", "aspect_ratios", "qa_rule_codes", 
    "risk_level", "fallback_preset_id"
]

async def seed():
    postgres_url = os.getenv("POSTGRES_URL") or settings.POSTGRES_URL
    if postgres_url.startswith("postgresql://"):
        postgres_url = postgres_url.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(postgres_url)
    
    if "sqlite" in postgres_url:
        from app.models.db import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False)


    csv_path = os.path.join(os.path.dirname(__file__), "app", "schemas", "pose_presets.csv")
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        return

    async with async_session() as session:
        # Load existing presets to prevent duplicates
        res = await session.execute(select(AngleShot))
        existing_shots = {s.code: s for s in res.scalars().all() if s.code}

        presets_to_add = []
        compats_to_add = []
        versions_to_add = []

        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row["preset_id"].strip()
                if code in existing_shots:
                    # Update existing preset
                    shot = existing_shots[code]
                    shot.name = row["display_name"].strip()
                    shot.category = row["family"].strip()
                    shot.framing = row["framing"].strip()
                    shot.pose = row["subfamily"].strip()
                    shot.camera_yaw = float(row["camera_yaw_deg"]) if row["camera_yaw_deg"] else None
                    shot.camera_pitch = float(row["camera_pitch_deg"]) if row["camera_pitch_deg"] else None
                    shot.focal_length_mm = float(row["lens_min_mm"]) if row["lens_min_mm"] else None
                    shot.is_premium = row["tier"].strip().upper() == "EXPANSION"
                    shot.sort_order = int(row["sort_order"]) if row["sort_order"] else 0
                    shot.status = "active" if row["status"].strip().upper() == "ACTIVE" else "archived"
                    
                    # Store meta keys
                    shot.quality_rules = {k: row[k].strip() for k in METADATA_KEYS if k in row}
                    print(f"Updated existing preset: {code}")
                else:
                    # Create new preset
                    shot = AngleShot(
                        name=row["display_name"].strip(),
                        code=code,
                        category=row["family"].strip(),
                        framing=row["framing"].strip(),
                        pose=row["subfamily"].strip(),
                        camera_yaw=float(row["camera_yaw_deg"]) if row["camera_yaw_deg"] else None,
                        camera_pitch=float(row["camera_pitch_deg"]) if row["camera_pitch_deg"] else None,
                        focal_length_mm=float(row["lens_min_mm"]) if row["lens_min_mm"] else None,
                        is_custom=False,
                        is_premium=row["tier"].strip().upper() == "EXPANSION",
                        is_visible=True,
                        status="active" if row["status"].strip().upper() == "ACTIVE" else "archived",
                        sort_order=int(row["sort_order"]) if row["sort_order"] else 0,
                        version=1,
                        quality_rules={k: row[k].strip() for k in METADATA_KEYS if k in row}
                    )
                    presets_to_add.append(shot)
                    session.add(shot)

        # Flush to generate IDs for new presets
        if presets_to_add:
            await session.flush()

        # Add compatibilities and version logs for new/updated presets
        for shot in presets_to_add + list(existing_shots.values()):
            # Find the row in CSV again for this shot to build associations
            with open(csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row["preset_id"].strip() == shot.code:
                        # Clear old compatibilities first if updating
                        if shot.id in [s.id for s in existing_shots.values()]:
                            await session.execute(
                                select(AngleShotCompatibility).where(
                                    AngleShotCompatibility.angle_shot_id == shot.id
                                )
                            )
                            # Delete existing compat records to overwrite
                            from sqlalchemy import delete
                            await session.execute(
                                delete(AngleShotCompatibility).where(
                                    AngleShotCompatibility.angle_shot_id == shot.id
                                )
                            )

                        # Build product types compatibility
                        comp_products = row["compatible_products"].strip()
                        if comp_products:
                            for p_type in comp_products.split("|"):
                                compats_to_add.append(
                                    AngleShotCompatibility(
                                        angle_shot_id=shot.id,
                                        product_type=p_type.strip().upper(),
                                        compatible=True
                                    )
                                )
                        
                        # Add initial version snapshot if new
                        if shot in presets_to_add:
                            versions_to_add.append(
                                AngleShotVersion(
                                    angle_shot_id=shot.id,
                                    version=1,
                                    configuration={
                                        "name": shot.name,
                                        "category": shot.category,
                                        "framing": shot.framing,
                                        "pose": shot.pose,
                                        "camera_yaw": shot.camera_yaw,
                                        "camera_pitch": shot.camera_pitch,
                                        "focal_length_mm": shot.focal_length_mm,
                                        "quality_rules": shot.quality_rules
                                    },
                                    change_note="Initial library seed version"
                                )
                            )
                        break

        # Save all and commit
        if compats_to_add:
            session.add_all(compats_to_add)
        if versions_to_add:
            session.add_all(versions_to_add)
            
        await session.commit()
        print(f"Successfully seeded/updated {len(presets_to_add)} new presets and {len(existing_shots)} existing presets!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed())
