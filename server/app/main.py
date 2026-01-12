"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routes import websocket, api
from app.services.session_manager import SessionManager


# Configure structured logging
def configure_logging(log_level: str) -> None:
    """Configure structlog for JSON logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level),
    )


# Application state
session_manager: SessionManager | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    global session_manager

    settings = get_settings()
    configure_logging(settings.log_level)

    log = structlog.get_logger()
    log.info("Starting Realtime Copilot server",
             host=settings.server_host,
             port=settings.server_port)

    # Initialize services
    session_manager = SessionManager()
    app.state.session_manager = session_manager

    log.info("Server started successfully")

    yield

    # Cleanup
    log.info("Shutting down server")
    if session_manager:
        await session_manager.shutdown()
    log.info("Server shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Realtime Interview & Meeting Copilot",
    description="Real-time transcription and AI-powered hints for interviews and meetings",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware (allow all for POC)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(websocket.router)
app.include_router(api.router, prefix="/api")

# Static files (client build) - will be available after client build
# Uncomment when client is built:
# app.mount("/", StaticFiles(directory="static", html=True), name="static")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}
