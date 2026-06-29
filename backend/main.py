"""
TaxFlow CRM — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger

from .config import get_settings
from .db import init_db
from .auth import router as auth_router
from .routes.clients import router as clients_router, users_router
from .routes.documents import router as documents_router
from .routes.deadlines import router as deadlines_router
from .routes.messages import router as messages_router, portal_router as portal_messages_router
from .routes.assistant import router as assistant_router
from .routes.dashboard import router as dashboard_router
from .routes.tasks import router as tasks_router

settings = get_settings()

# ─── App Lifespan ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name}...")
    await init_db()
    logger.info(f"Database initialized at {settings.database_url}")
    yield
    logger.info("TaxFlow CRM shutting down.")


# ─── FastAPI App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="TaxFlow CRM API",
    description="AI-powered CRM for US tax professionals and CPA firms",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API Routes ───────────────────────────────────────────────────────────────

API_PREFIX = "/api"

app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(clients_router, prefix=API_PREFIX)
app.include_router(users_router, prefix=API_PREFIX)
app.include_router(documents_router, prefix=API_PREFIX)
app.include_router(deadlines_router, prefix=API_PREFIX)
app.include_router(messages_router, prefix=API_PREFIX)
app.include_router(portal_messages_router, prefix=API_PREFIX)
app.include_router(assistant_router, prefix=API_PREFIX)
app.include_router(dashboard_router, prefix=API_PREFIX)
app.include_router(tasks_router, prefix=API_PREFIX)


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0",
        "ai_provider": settings.ai_provider,
        "ai_configured": bool(settings.ai_api_key),
    }


# ─── Frontend Static Files ────────────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

if FRONTEND_DIR.exists():
    # Serve CSS/JS as static
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def serve_index():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/clients")
    async def serve_clients():
        return FileResponse(FRONTEND_DIR / "clients.html")

    @app.get("/clients/{client_id}")
    async def serve_client_detail(client_id: int):
        return FileResponse(FRONTEND_DIR / "client_detail.html")

    @app.get("/messages")
    async def serve_messages():
        return FileResponse(FRONTEND_DIR / "messages.html")

    @app.get("/assistant")
    async def serve_assistant():
        return FileResponse(FRONTEND_DIR / "assistant.html")

    @app.get("/portal")
    async def serve_portal():
        return FileResponse(FRONTEND_DIR / "portal.html")

    @app.get("/login")
    async def serve_login():
        return FileResponse(FRONTEND_DIR / "index.html")
