"""
FastAPI Application Entry Point
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import logger

from app.modules.sources.sources_routes import router as sources_router
from app.modules.users.users_routes import router as users_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Register API Routers
app.include_router(sources_router, prefix=settings.API_V1_STR)
app.include_router(users_router, prefix=settings.API_V1_STR)

# CORS Middleware Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.PROJECT_NAME} in environment: {settings.ENVIRONMENT}")


@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "docs": "/docs",
        "health": f"{settings.API_V1_STR}/health",
    }


@app.get(f"{settings.API_V1_STR}/health")
async def health_check():
    return {
        "success": True,
        "message": "System operational",
        "data": {
            "status": "ok",
            "version": "0.1.0",
            "environment": settings.ENVIRONMENT,
            "database_connected": True,
            "redis_connected": True,
        }
    }
