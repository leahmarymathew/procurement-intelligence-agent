from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import init_db
from .routers import audit, metrics, procurement, pilot


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _seed_if_empty()
    if settings.groq_api_key:
        try:
            from .rag.knowledge_base import build_knowledge_base
            count = await build_knowledge_base()
            print(f"[startup] knowledge base ready: {count} chunks")
        except Exception as exc:
            print(f"[startup] knowledge base skipped: {exc}")
    yield


async def _seed_if_empty():
    from pathlib import Path
    import json
    from .database import AsyncSessionLocal
    from .models import PolicyRule, PilotMetrics
    from sqlalchemy import select

    seed_dir = Path(settings.seed_dir)
    if not seed_dir.exists():
        return

    async with AsyncSessionLocal() as db:
        # Seed policy rules
        result = await db.execute(select(PolicyRule).limit(1))
        if not result.scalar_one_or_none():
            rules_file = seed_dir / "policy_rules.json"
            if rules_file.exists():
                rules = json.loads(rules_file.read_text())
                for r in rules:
                    db.add(PolicyRule(**r))
                await db.commit()
                print(f"[startup] seeded {len(rules)} policy rules")

        # Seed pilot teams
        result = await db.execute(select(PilotMetrics).limit(1))
        if not result.scalar_one_or_none():
            pilots_file = seed_dir / "pilot_teams.json"
            if pilots_file.exists():
                pilots = json.loads(pilots_file.read_text())
                for p in pilots:
                    db.add(PilotMetrics(**p))
                await db.commit()
                print(f"[startup] seeded {len(pilots)} pilot teams")


app = FastAPI(
    title="Source-to-Pay Procurement Agent API",
    version="1.0.0",
    description="Multi-agent S2P system: supplier scoring, approval routing, process discovery, metrics.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(audit.router, prefix="/audit-log", tags=["Audit"])
app.include_router(metrics.router, prefix="/metrics", tags=["Metrics"])
app.include_router(procurement.router, prefix="/procurement", tags=["Procurement"])
app.include_router(pilot.router, prefix="/pilot", tags=["Pilot"])


@app.get("/health", tags=["System"])
async def health():
    return {
        "status": "ok",
        "system": "procurement-agent-v1.0",
        "prompt_library_version": settings.prompt_library_version,
    }
