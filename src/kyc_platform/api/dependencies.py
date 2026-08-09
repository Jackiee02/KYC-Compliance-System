from collections.abc import Generator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from kyc_platform.infrastructure.database import Database
from kyc_platform.services.evaluation import BenchmarkEvaluationService
from kyc_platform.services.pipeline import PipelineService
from kyc_platform.services.risk import RiskEngine
from kyc_platform.services.sanctions import ScreeningEngine


def get_database(request: Request) -> Database:
    return request.app.state.database


def get_session(database: Database = Depends(get_database)) -> Generator[Session, None, None]:
    with database.session() as session:
        yield session


def get_screening_engine(request: Request) -> ScreeningEngine:
    return request.app.state.screening_engine


def get_risk_engine(request: Request) -> RiskEngine:
    return request.app.state.risk_engine


def get_pipeline_service(request: Request) -> PipelineService:
    return request.app.state.pipeline_service


def get_evaluation_service(request: Request) -> BenchmarkEvaluationService:
    return request.app.state.evaluation_service
