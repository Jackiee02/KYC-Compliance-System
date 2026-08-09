from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EntityType(str, Enum):
    LEGAL_ENTITY = "legal_entity"
    INDIVIDUAL = "individual"
    LEGAL_ARRANGEMENT = "legal_arrangement"


class RiskCategory(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CustomerRecord(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    record_id: str = Field(default_factory=lambda: str(uuid4()))
    entity_type: EntityType = EntityType.LEGAL_ENTITY
    legal_name: str = Field(min_length=1, max_length=500)
    aliases: list[str] = Field(default_factory=list)
    registered_country: Optional[str] = Field(default=None, min_length=2, max_length=2)
    registration_number: Optional[str] = Field(default=None, max_length=100)
    lei: Optional[str] = Field(default=None, max_length=20)
    incorporation_date: Optional[date] = None
    last_kyc_review: Optional[date] = None
    aum_usd_millions: Optional[float] = Field(default=None, ge=0)
    is_pep: bool = False
    source: str = "unknown"
    source_reference: Optional[str] = None
    extra_data: dict[str, Any] = Field(default_factory=dict)


class NormalizedCustomer(CustomerRecord):
    normalized_name: str
    normalized_aliases: list[str] = Field(default_factory=list)
    normalized_registration_number: Optional[str] = None
    lei_valid: bool = False


class SanctionsEntity(BaseModel):
    entity_id: str
    source: str
    primary_name: str
    aliases: list[str] = Field(default_factory=list)
    entity_type: Optional[str] = None
    countries: list[str] = Field(default_factory=list)
    programs: list[str] = Field(default_factory=list)
    identifiers: dict[str, str] = Field(default_factory=dict)
    remarks: Optional[str] = None


class SanctionsDataset(BaseModel):
    source: str
    version: str
    retrieved_at: datetime = Field(default_factory=utc_now)
    content_sha256: str
    entities: list[SanctionsEntity]


class ScreeningMatch(BaseModel):
    entity_id: str
    source: str
    matched_name: str
    score: float = Field(ge=0, le=1)
    decision: str
    components: dict[str, float]
    programs: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class ScreeningResult(BaseModel):
    customer_record_id: str
    dataset_source: str
    dataset_version: str
    screened_at: datetime = Field(default_factory=utc_now)
    threshold: float
    matches: list[ScreeningMatch] = Field(default_factory=list)

    @property
    def top_score(self) -> float:
        return max((match.score for match in self.matches), default=0.0)


class RiskFactor(BaseModel):
    code: str
    value: float
    weight: float
    contribution: float
    explanation: str


class RiskAssessment(BaseModel):
    customer_record_id: str
    policy_version: str
    assessed_at: datetime = Field(default_factory=utc_now)
    score: float = Field(ge=0, le=100)
    category: RiskCategory
    factors: list[RiskFactor]
    recommended_review_date: date
    rationale: list[str]


class DuplicateCandidate(BaseModel):
    left_record_id: str
    right_record_id: str
    score: float = Field(ge=0, le=1)
    components: dict[str, float]
    recommendation: str = "manual_review"


class ArtifactRecord(BaseModel):
    path: str
    sha256: str
    media_type: str
    row_count: Optional[int] = None


class PipelineManifest(BaseModel):
    run_id: str
    started_at: datetime
    completed_at: datetime
    status: str
    record_count: int
    policy_version: str
    sanctions_source: str
    sanctions_version: str
    offline: bool
    configuration: dict[str, Any]
    summary: dict[str, Any]
    artifacts: list[ArtifactRecord]


class PipelineRunResult(BaseModel):
    run_id: str
    output_directory: str
    manifest_path: str
    summary: dict[str, Any]
