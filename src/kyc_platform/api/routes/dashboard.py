from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from kyc_platform.api.dependencies import get_risk_engine, get_screening_engine, get_session
from kyc_platform.api.schemas import DashboardResponse
from kyc_platform.infrastructure.database import AuditRepository, CustomerRepository, ScreeningCaseRepository
from kyc_platform.services.risk import RiskEngine
from kyc_platform.services.sanctions import ScreeningEngine

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def dashboard_summary(
    request: Request,
    session: Session = Depends(get_session),
    screening_engine: ScreeningEngine = Depends(get_screening_engine),
    risk_engine: RiskEngine = Depends(get_risk_engine),
) -> DashboardResponse:
    customers = CustomerRepository(session)
    cases = ScreeningCaseRepository(session)
    dataset = screening_engine.dataset
    return DashboardResponse(
        customer_count=customers.count(),
        pep_count=customers.count_pep(),
        active_case_count=cases.count_active(),
        open_case_count=cases.count_open(),
        audit_event_count=AuditRepository(session).count(),
        sanctions_source=dataset.source,
        sanctions_version=dataset.version,
        risk_policy_version=risk_engine.policy.version,
        operating_mode="offline" if request.app.state.settings.offline else "online",
    )
