from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from kyc_platform.domain.models import CustomerRecord, PipelineRunResult, RiskAssessment, ScreeningResult


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    sanctions_dataset_version: Optional[str] = None


class CustomerResponse(BaseModel):
    id: str
    record_id: str
    entity_type: str
    legal_name: str
    normalized_name: str
    aliases: list[str]
    registered_country: Optional[str]
    registration_number: Optional[str]
    lei: Optional[str]
    incorporation_date: Optional[date]
    last_kyc_review: Optional[date]
    aum_usd_millions: Optional[float]
    is_pep: bool
    source: str
    extra_data: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class ScreeningRequest(BaseModel):
    customer: CustomerRecord
    top_k: int = Field(default=5, ge=1, le=20)


class RiskRequest(BaseModel):
    customer: CustomerRecord


class RiskResponse(BaseModel):
    screening: ScreeningResult
    assessment: RiskAssessment


class PipelineRunRequest(BaseModel):
    record_count: int = Field(default=100, ge=1, le=10_000)
    offline: Optional[bool] = None
    duplicate_rate: float = Field(default=0.03, ge=0, le=0.5)
    sanctions_injection_rate: float = Field(default=0.005, ge=0, le=0.5)
    seed: int = 2026


class PipelineRunResponse(PipelineRunResult):
    pass


class CustomerAssessmentResponse(RiskResponse):
    cases_created: int


class CaseCustomerResponse(BaseModel):
    id: str
    record_id: str
    legal_name: str
    registered_country: Optional[str]
    is_pep: bool

    model_config = {"from_attributes": True}


class ScreeningCaseResponse(BaseModel):
    id: str
    status: str
    source: str
    dataset_version: str
    matched_entity_id: str
    matched_name: str
    score: float
    decision: Optional[str]
    evidence: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    customer: CaseCustomerResponse

    model_config = {"from_attributes": True}


class CaseDecisionRequest(BaseModel):
    decision: Literal["false_positive", "confirmed_match", "escalate"]
    notes: Optional[str] = Field(default=None, max_length=2_000)


class DashboardResponse(BaseModel):
    customer_count: int
    pep_count: int
    active_case_count: int
    open_case_count: int
    audit_event_count: int
    sanctions_source: str
    sanctions_version: str
    risk_policy_version: str
    operating_mode: str
