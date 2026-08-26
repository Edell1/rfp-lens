from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.core.config import Settings, get_settings
from app.projects.router import router as projects_router


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved_settings.validate_runtime()
        app.state.settings = resolved_settings
        yield

    app = FastAPI(title="RFP Lens", version="0.1.0", lifespan=lifespan)
    app.dependency_overrides[get_settings] = lambda: resolved_settings
    app.include_router(auth_router)
    app.include_router(projects_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
