from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from kyc_platform.api.dependencies import get_session
from kyc_platform.api.schemas import CaseDecisionRequest, ScreeningCaseResponse
from kyc_platform.infrastructure.database import AuditRepository, ScreeningCaseRepository

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


@router.get("", response_model=list[ScreeningCaseResponse])
def list_cases(
    case_status: Optional[Literal["open", "escalated", "closed"]] = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> list[ScreeningCaseResponse]:
    return [
        ScreeningCaseResponse.model_validate(case)
        for case in ScreeningCaseRepository(session).list(status=case_status, limit=limit)
    ]


@router.post("/{case_id}/decision", response_model=ScreeningCaseResponse)
def decide_case(
    case_id: str,
    payload: CaseDecisionRequest,
    session: Session = Depends(get_session),
    actor: str = Header(default="api-user", alias="X-Actor-ID"),
) -> ScreeningCaseResponse:
    repository = ScreeningCaseRepository(session)
    case = repository.get(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    decided = repository.decide(case, payload.decision, actor, payload.notes)
    AuditRepository(session).record(
        event_type="screening_case.decided",
        actor=actor,
        entity_type="screening_case",
        entity_id=case.id,
        payload={"decision": payload.decision, "notes": payload.notes or ""},
    )
    return ScreeningCaseResponse.model_validate(decided)
