from fastapi import FastAPI
from app.routers.auth import router as auth_router
from app.routers.assets import router as assets_router
from app.routers.brands import router as brands_router

app = FastAPI(
    title="ModeLens API",
    description="Backend API for ModeLens — Fashion AI Platform",
    version="1.0.0",
)

# Include Routers
app.include_router(auth_router)
app.include_router(assets_router)
app.include_router(brands_router)


@app.get("/")
async def root():
    return {"message": "Welcome to ModeLens API"}
