from fastapi import APIRouter, Depends, Request

from kyc_platform import __version__
from kyc_platform.api.dependencies import get_database
from kyc_platform.api.schemas import HealthResponse
from kyc_platform.infrastructure.database import Database

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthResponse)
def live(request: Request) -> HealthResponse:
    return HealthResponse(status="ok", service=request.app.title, version=__version__)


@router.get("/health/ready", response_model=HealthResponse)
def ready(request: Request, database: Database = Depends(get_database)) -> HealthResponse:
    database.ping()
    dataset_version = request.app.state.screening_engine.dataset.version
    return HealthResponse(
        status="ready",
        service=request.app.title,
        version=__version__,
        sanctions_dataset_version=dataset_version,
    )
