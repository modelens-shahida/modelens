import asyncio
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from pgvector.sqlalchemy import Vector

from sqlalchemy.dialects.postgresql import JSONB

# 1. Custom compile rule for pgvector's Vector type on SQLite
@compiles(Vector, "sqlite")
def compile_vector_sqlite(type_, compiler, **kw):
    return "TEXT"

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

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

# Test Database URL
TEST_DB_FILE = "./test_modelens.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"

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
    # Ensure any old test database is removed
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except PermissionError:
            pass

    test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    yield test_engine
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        
    await test_engine.dispose()
    
    # Clean up the test database file
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
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
