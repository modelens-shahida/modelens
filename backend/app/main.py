import logging
import os
import uuid
import time
from contextvars import ContextVar

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.config import settings
from app.routers.auth import router as auth_router
from app.routers.assets import router as assets_router
from app.routers.brands import router as brands_router
from app.routers.campaigns import router as campaigns_router
from app.routers.jobs import router as jobs_router
from app.routers.characters import router as characters_router
from app.routers.prompts import router as prompts_router
from app.routers.themes import router as themes_router
from app.routers.search import router as search_router
from app.routers.api_keys import router as api_keys_router
from app.routers.memory import brand_router, campaign_router
from app.routers.webhooks import router as webhooks_router
from app.routers.credits import router as credits_router
from app.routers.billing import router as billing_router
from app.routers.stripe_webhooks import router as stripe_webhooks_router
from app.routers.fix_requests import router as fix_requests_router
from app.routers.admin_stats import router as admin_stats_router
from app.routers.admin_settings import router as admin_settings_router
from app.routers.analytics import router as analytics_router
from app.routers.campaign_generation import router as campaign_generation_router
from app.routers.campaign_templates import router as campaign_templates_router
from app.routers.ghost_jobs import router as ghost_jobs_router
from app.routers.sketch_jobs import router as sketch_jobs_router
from app.routers.catalog_jobs import router as catalog_jobs_router
from app.routers.video_projects import router as video_projects_router, gen_router as generation_jobs_router
from app.routers.editorial_assets import router as editorial_assets_router
from app.routers.health import router as health_router
from app.routers.notifications import router as notifications_router
from app.services.pubsub_listener import redis_pubsub_listener
from app.routers.websockets import router as websockets_router
from app.routers.invites import router as invites_router
from app.middleware.api_versioning import APIVersionMiddleware
import app.services.metrics

# ContextVar to hold the request ID for the current async task execution
request_id_var: ContextVar[str] = ContextVar("request_id", default="")


# Configure Logging
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] [ReqID: %(request_id)s] - %(message)s"
)
logger = logging.getLogger("modelens")

# Attach the filter to the root logger handlers to include request ID in every log line
for handler in logging.getLogger().handlers:
    handler.addFilter(RequestIdFilter())

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    import asyncio
    asyncio.create_task(redis_pubsub_listener())
    yield
    # Shutdown
    try:
        from app.models.db import engine
        await engine.dispose()
        print("[App] Database connection pool closed.")
    except Exception as e:
        print(f"[App] DB pool close error: {e}")
    try:
        from app.middleware.rate_limit import redis_client
        await redis_client.aclose()
        print("[App] Redis connection closed.")
    except Exception as e:
        print(f"[App] Redis close error: {e}")

app = FastAPI(
    lifespan=lifespan,
    title="Mode Lens API",
    description="""
## Mode Lens — AI Fashion Content Production Platform

### Authentication
- `Authorization: Bearer <JWT token>` — for web dashboard users
- `X-API-Key: <api_key>` — for programmatic API access

### Rate Limiting
- Web users: 20 requests/minute on resource-heavy endpoints
- API key clients: 60 requests/minute (configurable per endpoint)
    """,
    version="1.0.0",
    contact={
        "name": "Mode Lens Engineering",
        "email": "modelens@shahidaparides.com",
    },
    openapi_tags=[
        {"name": "Auth", "description": "User registration, login, and profile management"},
        {"name": "Brands", "description": "Brand workspace management and member invitations"},
        {"name": "Assets", "description": "Asset upload, management, search, and soft-delete"},
        {"name": "Jobs", "description": "AI generation job submission and status tracking"},
        {"name": "Characters", "description": "Character identity library with versioning and LoRA training"},
        {"name": "Campaign Themes", "description": "Visual theme packages for campaign aesthetics"},
        {"name": "Prompts", "description": "Reusable prompt template management"},
        {"name": "Campaigns", "description": "Campaign management and asset linking"},
        {"name": "Search", "description": "Unified FTS + vector + hybrid search across assets"},
        {"name": "API Keys", "description": "Programmatic API key management"},
        {"name": "Webhooks", "description": "Brand webhook subscription management"},
        {"name": "Memory", "description": "Brand and campaign tag frequency analytics"},
    ],
)


# Request ID & Logging Middleware
class ProductionLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Retrieve or generate request ID
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request_id_var.set(req_id)
        
        start_time = time.time()
        logger.info(f"Incoming request: {request.method} {request.url.path}")
        
        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000
            logger.info(
                f"Request completed: {request.method} {request.url.path} "
                f"- Status: {response.status_code} - Time: {process_time:.2f}ms"
            )
            # Add Request ID back to the response headers
            response.headers["X-Request-ID"] = req_id
            return response
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"- Error: {str(e)} - Time: {process_time:.2f}ms",
                exc_info=True
            )
            # Re-raise to let the global exception handler format the response
            raise e

app.add_middleware(ProductionLoggingMiddleware)
app.add_middleware(APIVersionMiddleware)

# CORS Middleware Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure uploads directory exists and mount it
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Include Routers
app.include_router(auth_router)
app.include_router(assets_router)
app.include_router(brands_router)
app.include_router(campaigns_router)
app.include_router(jobs_router)
app.include_router(characters_router)
app.include_router(prompts_router)
app.include_router(themes_router)
app.include_router(search_router)
app.include_router(api_keys_router)
app.include_router(brand_router)
app.include_router(webhooks_router)
app.include_router(credits_router)
app.include_router(billing_router)
app.include_router(stripe_webhooks_router)
app.include_router(fix_requests_router)
app.include_router(admin_stats_router)
app.include_router(admin_settings_router)
app.include_router(analytics_router)
app.include_router(campaign_generation_router)
app.include_router(campaign_templates_router)
app.include_router(ghost_jobs_router)
app.include_router(sketch_jobs_router)
app.include_router(catalog_jobs_router)
app.include_router(video_projects_router)
app.include_router(generation_jobs_router)
app.include_router(editorial_assets_router)
app.include_router(health_router)
app.include_router(notifications_router)
app.include_router(websockets_router)
app.include_router(invites_router)
app.include_router(campaign_router)



# --- Global Exception Handlers ---

@app.exception_handler(IntegrityError)
async def db_integrity_exception_handler(request: Request, exc: IntegrityError):
    """Graceful handler for database unique constraints or foreign key violations."""
    req_id = request_id_var.get()
    err_msg = str(exc.orig) if exc.orig else str(exc)
    
    # Custom parsing to make error message client-safe
    detail_message = "A database integrity constraint has been violated."
    if "unique constraint" in err_msg.lower() or "unique" in err_msg.lower():
        detail_message = "A resource with this identifier already exists (e.g. email or key)."
    elif "foreign key" in err_msg.lower():
        detail_message = "Referenced parent record not found."

    logger.warning(f"Database integrity error: {err_msg} [RequestID: {req_id}]")
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "DatabaseIntegrityError",
            "detail": detail_message,
            "request_id": req_id
        }
    )

@app.exception_handler(SQLAlchemyError)
async def db_general_exception_handler(request: Request, exc: SQLAlchemyError):
    """Graceful handler for general database errors."""
    req_id = request_id_var.get()
    logger.error(f"General database error: {str(exc)} [RequestID: {req_id}]", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "DatabaseError",
            "detail": "An internal database error occurred. Please try again later.",
            "request_id": req_id
        }
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all handler for unhandled internal server errors."""
    req_id = request_id_var.get()
    logger.error(f"Unhandled server error: {str(exc)} [RequestID: {req_id}]", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "detail": "An unexpected error occurred. Please contact support with the Request ID.",
            "request_id": req_id
        }
    )


@app.get("/")
async def root():
    return {"message": "Welcome to ModeLens API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/metrics")
async def metrics():
    from fastapi import Response
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
