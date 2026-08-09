from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from kyc_platform.api.dependencies import get_risk_engine, get_screening_engine, get_session
from kyc_platform.api.schemas import CustomerAssessmentResponse, CustomerResponse
from kyc_platform.domain.models import CustomerRecord
from kyc_platform.infrastructure.database import (
    AuditRepository,
    CustomerORM,
    CustomerRepository,
    ScreeningCaseRepository,
)
from kyc_platform.services.normalization import normalize_customer
from kyc_platform.services.risk import RiskEngine
from kyc_platform.services.sanctions import ScreeningEngine

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerRecord,
    session: Session = Depends(get_session),
    actor: str = Header(default="api-user", alias="X-Actor-ID"),
) -> CustomerResponse:
    repository = CustomerRepository(session)
    try:
        customer = repository.create(normalize_customer(payload))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    AuditRepository(session).record(
        event_type="customer.created",
        actor=actor,
        entity_type="customer",
        entity_id=customer.id,
        payload={"record_id": customer.record_id},
    )
    return CustomerResponse.model_validate(customer)


@router.get("", response_model=list[CustomerResponse])
def list_customers(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    query: str = Query(default="", max_length=200),
    country: str = Query(default="", min_length=0, max_length=2),
    is_pep: Optional[bool] = Query(default=None),
    session: Session = Depends(get_session),
) -> list[CustomerResponse]:
    customers = CustomerRepository(session).list(
        offset,
        limit,
        query=query or None,
        country=country or None,
        is_pep=is_pep,
    )
    return [CustomerResponse.model_validate(customer) for customer in customers]


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(customer_id: str, session: Session = Depends(get_session)) -> CustomerResponse:
    customer = CustomerRepository(session).get(customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return CustomerResponse.model_validate(customer)


def _to_customer_record(customer: CustomerORM) -> CustomerRecord:
    return CustomerRecord(
        record_id=customer.record_id,
        entity_type=customer.entity_type,
        legal_name=customer.legal_name,
        aliases=customer.aliases,
        registered_country=customer.registered_country,
        registration_number=customer.registration_number,
        lei=customer.lei,
        incorporation_date=customer.incorporation_date,
        last_kyc_review=customer.last_kyc_review,
        aum_usd_millions=customer.aum_usd_millions,
        is_pep=customer.is_pep,
        source=customer.source,
        extra_data=customer.extra_data,
    )


@router.post("/{customer_id}/assessment", response_model=CustomerAssessmentResponse)
def assess_saved_customer(
    customer_id: str,
    session: Session = Depends(get_session),
    screening_engine: ScreeningEngine = Depends(get_screening_engine),
    risk_engine: RiskEngine = Depends(get_risk_engine),
    actor: str = Header(default="api-user", alias="X-Actor-ID"),
) -> CustomerAssessmentResponse:
    customer = CustomerRepository(session).get(customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    normalized = normalize_customer(_to_customer_record(customer))
    screening = screening_engine.screen(normalized)
    assessment = risk_engine.assess(normalized, screening)
    case_repository = ScreeningCaseRepository(session)
    cases_created = sum(
        case_repository.create_if_absent(customer.id, screening, match)[1] for match in screening.matches
    )
    AuditRepository(session).record(
        event_type="customer.assessed",
        actor=actor,
        entity_type="customer",
        entity_id=customer.id,
        payload={
            "record_id": customer.record_id,
            "risk_score": assessment.score,
            "risk_category": assessment.category.value,
            "screening_matches": len(screening.matches),
            "cases_created": cases_created,
        },
    )
    return CustomerAssessmentResponse(
        screening=screening,
        assessment=assessment,
        cases_created=cases_created,
    )
