import asyncio
import os
import pytest
import pytest_asyncio
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from pgvector.sqlalchemy import Vector

from sqlalchemy.dialects.postgresql import JSONB

from unittest.mock import MagicMock
import sys

# Global MLflow mock to prevent real HTTP connection attempts during test runs
mock_mlflow = MagicMock()
mock_run = MagicMock()
mock_run.info.run_id = "mock_global_run_id"
mock_mlflow.start_run.return_value = mock_run
mock_mlflow.start_run.return_value.__enter__.return_value = mock_run
mock_mlflow.start_run.return_value.__exit__.return_value = False
sys.modules["mlflow"] = mock_mlflow

# Global Celery task delay mock to prevent real Redis/broker connections during test runs
import celery.app.task
celery.app.task.Task.delay = MagicMock()
celery.app.task.Task.apply_async = MagicMock()
# Global Redis mock to prevent real Redis socket connections and timeouts
class MockRedisPipeline:
    def __init__(self, client):
        self.client = client
        self.key = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def zremrangebyscore(self, key, min_val, max_val):
        self.key = key
        if key not in self.client.store:
            self.client.store[key] = []
        self.client.store[key] = [t for t in self.client.store[key] if t > max_val]

    def zcard(self, key):
        self.key = key

    def zadd(self, key, mapping):
        self.key = key
        if key not in self.client.store:
            self.client.store[key] = []
        for val in mapping.values():
            self.client.store[key].append(val)

    def expire(self, key, seconds):
        self.key = key

    async def execute(self):
        count = len(self.client.store.get(self.key, [])) if self.key else 0
        return (None, count, None, None)

class MockRedisClient:
    def __init__(self):
        self.store = {}

    def pipeline(self, transaction=True):
        return MockRedisPipeline(self)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        return True

    async def setex(self, key, time, value):
        self.store[key] = value
        return True

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, key):
        self.store.pop(key, None)
        return True

    async def ping(self):
        return True

    async def close(self):
        pass

    async def aclose(self):
        pass

# Initialize global mock redis client
global_mock_redis = MockRedisClient()

import app.middleware.rate_limit
app.middleware.rate_limit.redis_client = global_mock_redis

import app.services.cache_service
app.services.cache_service.redis_client = global_mock_redis

import app.routers.jobs
app.routers.jobs.redis_client = global_mock_redis

import app.worker
app.worker.redis_client = global_mock_redis




@pytest.fixture(autouse=True)
def clear_mock_redis():
    global_mock_redis.store.clear()
    yield

# 1. Custom compile rule for pgvector's Vector type on SQLite
@compiles(Vector, "sqlite")
def compile_vector_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


# Proxy session maker to redirect all module-level session creations to the active test database
class TestSessionMakerProxy:
    def __init__(self):
        self.actual_maker = None

    def __call__(self, **kwargs):
        if self.actual_maker is None:
            raise RuntimeError("TestSessionMakerProxy: actual_maker not initialized yet")
        return self.actual_maker(**kwargs)

    def configure(self, **kwargs):
        if self.actual_maker:
            self.actual_maker.configure(**kwargs)


import app.models.db
proxy_session_maker = TestSessionMakerProxy()
app.models.db.async_session_maker = proxy_session_maker


# 2. Import Base and strip PostgreSQL-specific indexes before any table creation
from app.models.db import Base, get_db, User, Brand, BrandMember, Campaign, WorkflowTemplate
from app.middleware.auth import hash_password, create_access_token
from app.main import app

# Strip PostgreSQL indexes that use unsupported options or FTS functions
indexes_to_remove = []
for table in Base.metadata.tables.values():
    for index in list(table.indexes):
        dialect_options = index.dialect_options.get("postgresql", {})
        expr_str = ""
        # Inspect index expressions to see if they use pg features
        if hasattr(index, "expressions"):
            expr_str = " ".join(str(expr) for expr in index.expressions).lower()
        
        is_pg_only = (
            bool(dialect_options) 
            or "tsvector" in expr_str 
            or "to_tsvector" in expr_str 
            or "vector" in expr_str
        )
        if is_pg_only:
            table.indexes.remove(index)

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Creates the tables in the test SQLite database and cleans it up at the end."""
    db_id = uuid.uuid4().hex
    db_file = f"./test_modelens_{db_id}.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    # Ensure any old test database is removed (shouldn't exist with unique name)
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except PermissionError:
            pass

    test_engine = create_async_engine(db_url, echo=False)
    
    proxy_session_maker.actual_maker = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        class_=AsyncSession
    )
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield test_engine
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        
    await test_engine.dispose()
    
    # Clean up the test database file
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except PermissionError:
            pass

@pytest_asyncio.fixture
async def db_session(setup_test_db) -> AsyncSession:
    """Provides a fresh database session for a test function."""
    test_engine = setup_test_db
    
    async_session = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
        class_=AsyncSession
    )
    
    async with async_session() as session:
        yield session

@pytest_asyncio.fixture(autouse=True)
async def override_db_dependency(db_session: AsyncSession):
    """Overrides the FastAPI get_db dependency to use the isolated test database session."""
    async def _override_get_db():
        try:
            yield db_session
        finally:
            pass
            
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

@pytest_asyncio.fixture
async def client() -> AsyncClient:
    """Provides a configured async test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

# --- Pre-populated Seed Data Fixture ---
@pytest_asyncio.fixture
async def test_data(db_session: AsyncSession):
    """Seed base users, brand, and memberships to test RBAC roles."""
    # 1. Create Users
    users_dict = {
        "owner": User(email="owner@brand.com", hashed_password=hash_password("password"), full_name="Owner User", role="user"),
        "admin": User(email="admin@brand.com", hashed_password=hash_password("password"), full_name="Admin User", role="user"),
        "editor": User(email="editor@brand.com", hashed_password=hash_password("password"), full_name="Editor User", role="user"),
        "viewer": User(email="viewer@brand.com", hashed_password=hash_password("password"), full_name="Viewer User", role="user"),
        "nonmember": User(email="nonmember@brand.com", hashed_password=hash_password("password"), full_name="Non Member", role="user"),
    }
    
    for u in users_dict.values():
        db_session.add(u)
    await db_session.commit()
    
    # 2. Create Brands
    brand = Brand(name="Test Brand", owner_id=users_dict["owner"].id)
    other_brand = Brand(name="Other Brand", owner_id=users_dict["nonmember"].id)
    db_session.add(brand)
    db_session.add(other_brand)
    await db_session.commit()
    
    # 3. Create Brand Memberships
    memberships = [
        BrandMember(brand_id=brand.id, user_id=users_dict["admin"].id, role="admin"),
        BrandMember(brand_id=brand.id, user_id=users_dict["editor"].id, role="editor"),
        BrandMember(brand_id=brand.id, user_id=users_dict["viewer"].id, role="viewer"),
    ]
    
    for m in memberships:
        db_session.add(m)
    await db_session.commit()
    
    # 4. Create a Workflow Template
    workflow = WorkflowTemplate(
        name="Standard Campaign Workflow",
        description="A template for testing campaign workflows.",
        workflow_json='{"steps": ["validate", "approve", "publish"]}'
    )
    db_session.add(workflow)
    await db_session.commit()
    
    # Helper for generating auth headers
    def get_auth_headers(user_role: str):
        user = users_dict[user_role]
        token = create_access_token({"sub": user.email})
        return {"Authorization": f"Bearer {token}"}
        
    return {
        "users": users_dict,
        "brand": brand,
        "other_brand": other_brand,
        "workflow": workflow,
        "get_headers": get_auth_headers
    }
