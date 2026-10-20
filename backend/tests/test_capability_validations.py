"""Capability validations (Character Runtime PR 1): lifecycle, ORM rules, uniqueness, backfill, migration.

The backfill must not change anything customers see: every customer option route returns the same bytes
before and after it, and none of them carries a technical field.
"""
import importlib.util
import os

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

import app.models.db as models
from app.migration_guard import table_differences
from app.models.db import AppearanceOption, CapabilityValidation, CapabilityValidationRuleError
from app.services import capability_validations as cv
from app.services import pose_resolver as pose_service
from test_production_dispatch import queue, world  # noqa: F401 (fixtures)

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATION = os.path.join(BACKEND, "alembic", "versions", "capability_validations_001.py")
CHARACTER = "EE-F-002"
PRODUCT_TYPES = ("garment", "shoes", "bags", "eyewear", "headwear", "jewelry")
CUSTOMER_ROUTES = (
    f"/api/v1/characters/{CHARACTER}/styling-options",
    f"/api/v1/characters/{CHARACTER}/capabilities",
    f"/api/v1/characters-v2/{CHARACTER}/current-version",
    *(f"/api/v1/characters/{CHARACTER}/poses?product_type={t}" for t in PRODUCT_TYPES),
    "/api/v1/presets/locations",
    "/api/v1/presets/lighting",
    "/api/v1/presets/campaigns",
)
# Never in a customer response (DESIGN.md section 0), plus this table's internals.
FORBIDDEN_TERMS = (
    "lora", "adapter", "checkpoint", "strength", "seed", "cfg", "provider", "comfyui", "workflow", "training",
    "safetensors", "validated_by", "promoted_by", "SYSTEM_BACKFILL", "capability_key", "capability_version",
)
ALL_PASS = {"identity": "PASS", "face": "PASS", "body": "PASS", "product": "PASS"}


def assert_no_forbidden_terms(raw: str):
    lowered = raw.lower()
    for term in FORBIDDEN_TERMS:
        assert term.lower() not in lowered, f"customer response contains {term!r}: {raw[:300]}"


def _migration():
    spec = importlib.util.spec_from_file_location("capability_validations_001", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _all(db):
    return list((await db.execute(select(CapabilityValidation).order_by(CapabilityValidation.id))).scalars().all())


def _keys(records):
    return {(r.capability_type, r.capability_key, r.capability_version, r.customer_id) for r in records}


def _plan_keys(plan):
    return sorted((p["character_id"], p["character_version"], p["capability_type"], p["capability_key"],
                   p["capability_version"], p["customer_id"], p["is_default"], p["sort_order"],
                   repr(sorted(p["validation"]["backfill"].items()))) for p in plan)


async def _register(db, key="SOFT_WAVES", version=1, customer_id="hair_soft_waves", capability_type="HAIR"):
    return await cv.register(db, character_id=CHARACTER, character_version="1.0", capability_type=capability_type,
                             capability_key=key, capability_version=version, customer_id=customer_id)


async def _validated(db, **kwargs):
    record = await _register(db, **kwargs)
    return await cv.record_validation(db, record, ALL_PASS, {"notes": "ok"}, "aryan@modelens.ai")


# ========================== Backfill ==============================

@pytest.mark.asyncio
async def test_backfill_promotes_everything_customers_can_use_today(db_session, world):
    created = await cv.backfill_promoted(db_session)
    records = await _all(db_session)
    assert len(created) == len(records) > 0
    assert all(r.status == "PROMOTED" for r in records)
    assert all((r.character_id, r.character_version) == (CHARACTER, "1.0") for r in records)
    assert all(r.validated_by == r.promoted_by == "SYSTEM_BACKFILL" and r.validated_at and r.promoted_at
               for r in records)
    by_type = {}
    for r in records:
        by_type.setdefault(r.capability_type, set()).add((r.capability_key, r.customer_id))

    assert by_type["HAIR"] == {("CANONICAL", "hair_canonical")}
    assert by_type["MAKEUP"] == {("NATURAL", "makeup_natural")}
    assert by_type["EXPRESSION"] == {("NEUTRAL_EDITORIAL", "expr_neutral_editorial")}
    assert by_type["PRODUCT_TYPE"] == {("garment", "garment")}  # the only PRODUCTION pack
    offered = await pose_service.customer_poses(db_session, CHARACTER, "garment")
    assert by_type["POSE"] == {(p.pose_id, f"pose_{p.pose_id}") for p, _ in offered}
    assert ("ENV-STU-0001", "scene_env-stu-0001") in by_type["SCENE"]
    assert ("STUDIO_SOFT_DIFFUSE", "lighting_studio_soft_diffuse") in by_type["LIGHTING"]
    assert ("ecommerce", "campaign_ecommerce") in by_type["CAMPAIGN"]
    assert set(by_type) == {"HAIR", "MAKEUP", "EXPRESSION", "PRODUCT_TYPE", "POSE", "SCENE", "LIGHTING", "CAMPAIGN"}

    hair = next(r for r in records if r.capability_type == "HAIR")
    assert hair.is_default and hair.validation == {"backfill": {
        "source": "appearance_options", "source_key": "EE-F-002_HAIR_CANONICAL_V1", "source_status": "PRODUCTION"}}
    defaults = {r.capability_key for r in records if r.capability_type == "SCENE" and r.is_default}
    assert defaults == {"ENV-STU-0001"}


@pytest.mark.asyncio
async def test_backfill_skips_nails_and_options_that_are_not_live(db_session, world):
    db_session.add_all([
        AppearanceOption(internal_key="EE-F-002_NAILS_NUDE_V1", character_id=CHARACTER, character_version="1.0",
                         category="NAILS", option_id="NUDE", version=1, label="Nude", status="PRODUCTION"),
        AppearanceOption(internal_key="EE-F-002_HAIR_SOFT-WAVES_V1", character_id=CHARACTER, character_version="1.0",
                         category="HAIR_STYLE", option_id="SOFT_WAVES", version=1, label="Soft Waves",
                         status="APPROVED"),
    ])
    await db_session.commit()
    await cv.backfill_promoted(db_session)
    keys = {r.capability_key for r in await _all(db_session)}
    assert "NUDE" not in keys and "SOFT_WAVES" not in keys
    # Packs that are not in PRODUCTION give no product type and no poses.
    customer_ids = {r.customer_id for r in await _all(db_session)}
    assert "shoes" not in customer_ids and "pose_foot_forward" not in customer_ids


@pytest.mark.asyncio
async def test_backfill_is_idempotent_and_never_changes_existing_records(db_session, world):
    # A record registered by hand before the backfill stays as it is.
    manual = await _register(db_session, key="CANONICAL", customer_id="hair_canonical")
    first = await cv.backfill_promoted(db_session)
    snapshot = [(r.id, r.status, r.updated_at, r.validated_by, r.promoted_by) for r in await _all(db_session)]
    assert "CANONICAL" not in {r.capability_key for r in first if r.capability_type == "HAIR"}

    assert await cv.backfill_promoted(db_session) == []
    assert await cv.backfill_promoted(db_session) == []
    after = [(r.id, r.status, r.updated_at, r.validated_by, r.promoted_by) for r in await _all(db_session)]
    assert after == snapshot
    await db_session.refresh(manual)
    assert (manual.status, manual.validated_by, manual.promoted_by) == ("REGISTERED", None, None)


@pytest.mark.asyncio
async def test_backfill_leaves_customer_responses_byte_identical(client, db_session, world):
    headers = world["h"]["viewer"]
    before = {}
    for path in CUSTOMER_ROUTES:
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 200, (path, resp.text)
        before[path] = resp.content
    assert await cv.backfill_promoted(db_session)
    for path in CUSTOMER_ROUTES:
        resp = await client.get(path, headers=headers)
        assert resp.status_code == 200
        assert resp.content == before[path], path


@pytest.mark.asyncio
async def test_customer_option_responses_carry_no_technical_fields(client, db_session, world):
    await cv.backfill_promoted(db_session)
    for path in CUSTOMER_ROUTES:
        resp = await client.get(path, headers=world["h"]["viewer"])
        assert resp.status_code == 200
        assert_no_forbidden_terms(resp.text)


# ========================== Lifecycle =============================

@pytest.mark.asyncio
async def test_validate_then_promote_records_both_actors(db_session, world):
    record = await _register(db_session)
    assert (record.status, record.is_default, record.recommended) == ("REGISTERED", False, False)
    record = await cv.start_validation(db_session, record)
    assert record.status == "VALIDATING"
    record = await cv.record_validation(db_session, record, ALL_PASS, {"sample_production_ids": ["prd_1"]},
                                        "aryan@modelens.ai")
    assert record.status == "VALIDATED"
    assert record.validation == {"checks": ALL_PASS, "evidence": {"sample_production_ids": ["prd_1"]}}
    assert record.validated_by == "aryan@modelens.ai" and record.validated_at
    record, replaced = await cv.promote(db_session, record, "anshu@modelens.ai", recommended=True)
    assert (record.status, record.promoted_by, record.recommended, replaced) == (
        "PROMOTED", "anshu@modelens.ai", True, None)
    assert record.promoted_at and record.validated_by == "aryan@modelens.ai"
    assert [r.id for r in await cv.promoted(db_session, CHARACTER, "1.0", "HAIR")] == [record.id]


@pytest.mark.asyncio
async def test_same_person_may_validate_and_promote_while_four_eyes_is_pending(db_session, world):
    record = await cv.record_validation(db_session, await _register(db_session), ALL_PASS, None, "anshu@modelens.ai")
    record, _ = await cv.promote(db_session, record, "anshu@modelens.ai")
    assert record.status == "PROMOTED" and record.validated_by == record.promoted_by


@pytest.mark.asyncio
async def test_failed_check_rejects_and_rework_goes_back_to_validating(db_session, world):
    record = await _register(db_session)
    record = await cv.record_validation(db_session, record, {**ALL_PASS, "face": "FAIL"}, None, "aryan@modelens.ai")
    assert record.status == "REJECTED"
    with pytest.raises(cv.CapabilityConflict):
        await cv.promote(db_session, record, "anshu@modelens.ai")
    record = await cv.start_validation(db_session, record)
    record = await cv.record_validation(db_session, record, ALL_PASS, None, "aryan@modelens.ai")
    assert record.status == "VALIDATED"


@pytest.mark.asyncio
@pytest.mark.parametrize("checks", [{"identity": "PASS"}, {**ALL_PASS, "face": "MAYBE"}, {**ALL_PASS, "extra": "PASS"}])
async def test_validation_needs_every_check(db_session, world, checks):
    with pytest.raises(cv.CapabilityInvalid):
        await cv.record_validation(db_session, await _register(db_session), checks, None, "aryan@modelens.ai")


@pytest.mark.asyncio
async def test_lifecycle_cannot_skip_steps_and_retired_is_final(db_session, world):
    record = await _register(db_session)
    with pytest.raises(cv.CapabilityConflict):
        await cv.promote(db_session, record, "anshu@modelens.ai")  # not validated
    with pytest.raises(cv.CapabilityInvalid):
        await cv.retire(db_session, record, "anshu@modelens.ai", "  ")
    record = await cv.retire(db_session, record, "anshu@modelens.ai", "Not needed.")
    assert (record.status, record.retired_by, record.retire_reason) == ("RETIRED", "anshu@modelens.ai", "Not needed.")
    for step in (cv.start_validation(db_session, record),
                 cv.record_validation(db_session, record, ALL_PASS, None, "aryan@modelens.ai")):
        with pytest.raises(cv.CapabilityConflict):
            await step


@pytest.mark.asyncio
async def test_promoting_a_new_version_retires_the_old_one_and_keeps_the_customer_id(db_session, world):
    v1 = await _validated(db_session)
    v1, _ = await cv.promote(db_session, v1, "anshu@modelens.ai", is_default=True)
    v2 = await _validated(db_session, version=2)  # same customer id while v1 is live
    v2, replaced = await cv.promote(db_session, v2, "anshu@modelens.ai", is_default=True)
    await db_session.refresh(v1)
    assert replaced.id == v1.id
    assert (v1.status, v1.is_default, v1.retire_reason) == ("RETIRED", False, "Replaced by version 2.")
    assert (v2.status, v2.is_default, v2.customer_id) == ("PROMOTED", True, "hair_soft_waves")
    assert [r.capability_version for r in await cv.promoted(db_session, CHARACTER, "1.0", "HAIR")] == [2]


@pytest.mark.asyncio
async def test_promoting_a_default_clears_the_old_default_of_the_type(db_session, world):
    first, _ = await cv.promote(db_session, await _validated(db_session), "anshu@modelens.ai", is_default=True)
    second, _ = await cv.promote(db_session, await _validated(db_session, key="SLEEK_BUN", customer_id="hair_sleek_bun"),
                                 "anshu@modelens.ai", is_default=True)
    await db_session.refresh(first)
    assert (first.status, first.is_default, second.is_default) == ("PROMOTED", False, True)


# ========================== Uniqueness and register rules =========

@pytest.mark.asyncio
async def test_register_rejects_duplicates_and_customer_ids_of_other_capabilities(db_session, world):
    await _register(db_session)
    with pytest.raises(cv.CapabilityConflict):
        await _register(db_session)
    with pytest.raises(cv.CapabilityConflict):
        await _register(db_session, key="OTHER", customer_id="hair_soft_waves")
    # A new version of the same capability may reuse its customer id.
    assert (await _register(db_session, version=2)).capability_version == 2


@pytest.mark.asyncio
async def test_retired_or_rejected_records_free_their_customer_id(db_session, world):
    old = await _register(db_session)
    await cv.retire(db_session, old, "anshu@modelens.ai", "Renamed.")
    assert (await _register(db_session, key="OTHER", customer_id="hair_soft_waves")).status == "REGISTERED"


@pytest.mark.asyncio
@pytest.mark.parametrize("field, value, error", [
    ("capability_type", "NAILS", cv.CapabilityInvalid),
    ("capability_key", "bad key!", cv.CapabilityInvalid),
    ("customer_id", "Hair_Soft", cv.CapabilityInvalid),
    ("capability_version", 0, cv.CapabilityInvalid),
    ("character_version", "9.9", cv.CapabilityNotFound),
])
async def test_register_validation(db_session, world, field, value, error):
    body = dict(character_id=CHARACTER, character_version="1.0", capability_type="HAIR", capability_key="SOFT_WAVES",
                capability_version=1, customer_id="hair_soft_waves")
    body[field] = value
    with pytest.raises(error):
        await cv.register(db_session, **body)


@pytest.mark.asyncio
async def test_unique_version_constraint_in_the_database(db_session, world):
    await _register(db_session)
    db_session.add(CapabilityValidation(character_id=CHARACTER, character_version="1.0", capability_type="HAIR",
                                        capability_key="SOFT_WAVES", capability_version=1, customer_id="hair_x"))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


# ========================== ORM rules =============================

@pytest.mark.asyncio
@pytest.mark.parametrize("field, value", [
    ("capability_key", "OTHER"), ("customer_id", "hair_other"), ("capability_version", 3),
    ("character_version", "2.0"), ("capability_type", "MAKEUP"), ("character_id", "EE-F-001"),
])
async def test_identity_fields_never_change(db_session, world, field, value):
    record = await _register(db_session)
    setattr(record, field, value)
    with pytest.raises(CapabilityValidationRuleError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_status_cannot_jump_past_the_lifecycle_through_the_orm(db_session, world):
    record = await _register(db_session)
    record.status = "PROMOTED"
    with pytest.raises(CapabilityValidationRuleError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_records_are_never_deleted_and_bulk_writes_are_refused(db_session, world):
    record = await _register(db_session)
    await db_session.delete(record)
    with pytest.raises(CapabilityValidationRuleError):
        await db_session.commit()
    await db_session.rollback()
    with pytest.raises(CapabilityValidationRuleError):
        await db_session.execute(update(CapabilityValidation).values(status="PROMOTED"))
    with pytest.raises(CapabilityValidationRuleError):
        await db_session.execute(sa.delete(CapabilityValidation))
    assert (await db_session.execute(select(func.count()).select_from(CapabilityValidation))).scalar() == 1


# ========================== Migration =============================

@pytest.mark.asyncio
async def test_migration_backfill_matches_the_service(db_session, world):
    migration = _migration()
    service_plan = await cv.backfill_plan(db_session)
    migration_plan = await db_session.run_sync(lambda s: migration.backfill_plan(s.connection()))
    assert _plan_keys(migration_plan) == _plan_keys(service_plan)

    inserted = await db_session.run_sync(lambda s: migration.backfill(s.connection()))
    await db_session.commit()
    assert inserted == len(service_plan)
    assert await db_session.run_sync(lambda s: migration.backfill(s.connection())) == 0  # re-run: nothing new
    assert await cv.backfill_promoted(db_session) == []  # the service agrees nothing is missing
    records = await _all(db_session)
    assert _keys(records) == {(p["capability_type"], p["capability_key"], p["capability_version"], p["customer_id"])
                              for p in service_plan}
    assert all(r.status == "PROMOTED" and r.promoted_by == "SYSTEM_BACKFILL" for r in records)


@pytest.fixture
def chain_db(tmp_path):
    """Every model table except capability_validations, as before this revision."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'chain.db'}")
    tables = [t for name, t in models.Base.metadata.tables.items() if name != "capability_validations"]
    models.Base.metadata.create_all(engine, tables=tables)
    yield engine
    engine.dispose()


def _run(engine, step):
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(_migration(), step)()


def test_migration_creates_the_model_table_and_is_rerunnable(chain_db):
    _run(chain_db, "upgrade")
    _run(chain_db, "upgrade")  # second run: table and indexes exist, nothing to backfill
    with chain_db.connect() as conn:
        assert table_differences(conn, "capability_validations",
                                 list(models.CapabilityValidation.__table__.columns)) == []
        indexes = {ix["name"]: ix for ix in sa.inspect(conn).get_indexes("capability_validations")}
    assert {"ix_capability_validations_lookup", "uq_capability_validation_promoted",
            "uq_capability_validation_customer_id", "ix_capability_validations_character_id"} <= set(indexes)
    assert indexes["uq_capability_validation_promoted"]["unique"]
    _run(chain_db, "downgrade")
    with chain_db.connect() as conn:
        assert not sa.inspect(conn).has_table("capability_validations")


def test_partial_unique_indexes_allow_one_promoted_version_and_customer_id(chain_db):
    _run(chain_db, "upgrade")
    row = dict(character_id=CHARACTER, character_version="1.0", capability_type="HAIR", capability_key="SOFT_WAVES",
               customer_id="hair_soft_waves", is_default=False, recommended=False, sort_order=0)
    table = sa.table("capability_validations", *[sa.column(c) for c in (*row, "capability_version", "status")])
    with chain_db.begin() as conn:
        conn.execute(table.insert().values(**row, capability_version=1, status="RETIRED"))
        conn.execute(table.insert().values(**row, capability_version=2, status="PROMOTED"))
        conn.execute(table.insert().values(**row, capability_version=3, status="REGISTERED"))
    for clash in ({**row, "capability_version": 4},  # second PROMOTED version of the capability
                  {**row, "capability_key": "OTHER", "capability_version": 1}):  # promoted customer id in use
        with pytest.raises(IntegrityError):
            with chain_db.begin() as conn:
                conn.execute(table.insert().values(**clash, status="PROMOTED"))


def test_single_alembic_head_is_this_revision():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config(os.path.join(BACKEND, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND, "alembic"))
    assert ScriptDirectory.from_config(cfg).get_heads() == ["capability_validations_001"]
