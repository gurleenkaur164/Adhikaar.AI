"""Adhikar.AI — FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .routers import applications, pipeline, schemes
from .services.scheme_repo import load_schemes

# create tables (SQLite by default). For Postgres in prod, prefer Alembic.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Adhikar.AI API",
    description="Agentic copilot for autonomous government-scheme extraction for CSC operators.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CLIENT_URL, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline.router)
app.include_router(schemes.router)
app.include_router(applications.router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "ai_enabled": settings.ai_enabled,
        "ai_model": settings.GROQ_MODEL if settings.ai_enabled else None,
        "extraction_mode": "groq" if settings.ai_enabled else "rule-based",
        "schemes_loaded": len(load_schemes()),
    }


@app.get("/")
def root():
    return {"message": "Adhikar.AI API — see /docs for the interactive API."}
