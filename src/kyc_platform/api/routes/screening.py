from fastapi import APIRouter, Depends

from kyc_platform.api.dependencies import get_risk_engine, get_screening_engine
from kyc_platform.api.schemas import RiskRequest, RiskResponse, ScreeningRequest
from kyc_platform.domain.models import ScreeningResult
from kyc_platform.services.normalization import normalize_customer
from kyc_platform.services.risk import RiskEngine
from kyc_platform.services.sanctions import ScreeningEngine

router = APIRouter(prefix="/api/v1", tags=["screening"])


@router.post("/screenings", response_model=ScreeningResult)
def screen_customer(
    payload: ScreeningRequest,
    engine: ScreeningEngine = Depends(get_screening_engine),
) -> ScreeningResult:
    return engine.screen(normalize_customer(payload.customer), top_k=payload.top_k)


@router.post("/risk-assessments", response_model=RiskResponse)
def assess_customer(
    payload: RiskRequest,
    screening_engine: ScreeningEngine = Depends(get_screening_engine),
    risk_engine: RiskEngine = Depends(get_risk_engine),
) -> RiskResponse:
    customer = normalize_customer(payload.customer)
    screening = screening_engine.screen(customer)
    return RiskResponse(screening=screening, assessment=risk_engine.assess(customer, screening))
