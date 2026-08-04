from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.container import Container
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.interfaces.api.cameras import create_cameras_router

configure_logging()

container = Container(settings)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await container.init_db()
    yield


app = FastAPI(title="VigilAI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(
    create_cameras_router(
        build_onboard_camera_use_case=container.build_onboard_camera_use_case,
        build_list_cameras_use_case=container.build_list_cameras_use_case,
        build_get_camera_use_case=container.build_get_camera_use_case,
    )
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
