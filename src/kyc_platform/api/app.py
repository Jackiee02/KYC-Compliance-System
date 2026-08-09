from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from kyc_platform import __version__
from kyc_platform.api.routes import cases, customers, dashboard, evaluations, health, pipeline, screening
from kyc_platform.config import Settings, get_settings
from kyc_platform.infrastructure.database import Database
from kyc_platform.logging import configure_logging
from kyc_platform.services.evaluation import BenchmarkEvaluationService
from kyc_platform.services.pipeline import PipelineService
from kyc_platform.services.risk import RiskEngine, RiskPolicy
from kyc_platform.services.sanctions import OFACSanctionsProvider, ScreeningEngine, offline_sanctions_dataset


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    application_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        configure_logging(application_settings.log_level)
        application_settings.ensure_directories()
        database = Database(application_settings.database_url)
        database.create_schema()
        policy = RiskPolicy.load(application_settings.risk_policy_path)
        dataset = (
            offline_sanctions_dataset()
            if application_settings.offline
            else OFACSanctionsProvider(application_settings.external_request_timeout_seconds).fetch(
                application_settings.data_dir / "sanctions"
            )
        )
        app.state.database = database
        app.state.settings = application_settings
        app.state.screening_engine = ScreeningEngine(
            dataset,
            review_threshold=application_settings.sanctions_review_threshold,
            match_threshold=application_settings.sanctions_match_threshold,
        )
        app.state.risk_engine = RiskEngine(policy)
        app.state.pipeline_service = PipelineService(application_settings, policy)
        app.state.evaluation_service = BenchmarkEvaluationService(
            dataset_path=application_settings.benchmark_dataset_path,
            policy=policy,
            review_threshold=application_settings.sanctions_review_threshold,
            match_threshold=application_settings.sanctions_match_threshold,
            output_root=application_settings.output_dir,
        )
        yield
        database.engine.dispose()

    app = FastAPI(
        title=application_settings.app_name,
        version=__version__,
        description="Auditable KYC/AML decision-support APIs. Automated outputs require human compliance review.",
        lifespan=lifespan,
    )
    app.include_router(health.router)
    app.include_router(dashboard.router)
    app.include_router(customers.router)
    app.include_router(screening.router)
    app.include_router(cases.router)
    app.include_router(pipeline.router)
    app.include_router(evaluations.router)

    web_root = Path(__file__).resolve().parents[1] / "web"
    app.mount("/static", StaticFiles(directory=web_root / "static", check_dir=False), name="static")
    app.mount(
        "/artifacts",
        StaticFiles(directory=application_settings.output_dir, check_dir=False),
        name="artifacts",
    )

    @app.get("/", include_in_schema=False, response_class=FileResponse)
    def workbench() -> FileResponse:
        return FileResponse(web_root / "index.html")

    return app


app = create_app()
