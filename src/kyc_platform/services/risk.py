from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from kyc_platform.domain.models import (
    EntityType,
    NormalizedCustomer,
    RiskAssessment,
    RiskCategory,
    RiskFactor,
    ScreeningResult,
)


class RiskPolicy(BaseModel):
    version: str
    description: str
    base_score: float = Field(ge=0, le=100)
    weights: dict[str, float]
    category_thresholds: dict[str, float]
    jurisdiction_tiers: dict[str, list[str]]
    review_period_days: dict[str, int]
    large_exposure_usd_millions: float

    @classmethod
    def load(cls, path: Path) -> "RiskPolicy":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


class RiskEngine:
    def __init__(self, policy: RiskPolicy) -> None:
        self.policy = policy

    def _category(self, score: float) -> RiskCategory:
        thresholds = self.policy.category_thresholds
        if score >= thresholds["critical"]:
            return RiskCategory.CRITICAL
        if score >= thresholds["high"]:
            return RiskCategory.HIGH
        if score >= thresholds["medium"]:
            return RiskCategory.MEDIUM
        return RiskCategory.LOW

    @staticmethod
    def _factor(code: str, value: float, weight: float, explanation: str) -> RiskFactor:
        return RiskFactor(
            code=code,
            value=round(value, 4),
            weight=weight,
            contribution=round(value * weight, 2),
            explanation=explanation,
        )

    def assess(
        self,
        customer: NormalizedCustomer,
        screening: ScreeningResult,
        as_of_date: Optional[date] = None,
    ) -> RiskAssessment:
        factors: list[RiskFactor] = []
        weights = self.policy.weights
        if screening.top_score > 0:
            factors.append(
                self._factor(
                    "sanctions_match",
                    screening.top_score,
                    weights["sanctions_match"],
                    "Potential sanctions match requires analyst review; it is not an automatic designation decision.",
                )
            )
        if customer.is_pep:
            factors.append(self._factor("pep", 1.0, weights["pep"], "Customer is marked as a PEP."))

        country = (customer.registered_country or "").upper()
        if country in self.policy.jurisdiction_tiers.get("high", []):
            factors.append(
                self._factor(
                    "high_risk_jurisdiction",
                    1.0,
                    weights["high_risk_jurisdiction"],
                    "Jurisdiction is in the policy's high-risk tier.",
                )
            )
        elif country in self.policy.jurisdiction_tiers.get("elevated", []):
            factors.append(
                self._factor(
                    "elevated_risk_jurisdiction",
                    1.0,
                    weights["elevated_risk_jurisdiction"],
                    "Jurisdiction is in the policy's elevated-risk tier.",
                )
            )

        if customer.entity_type == EntityType.LEGAL_ENTITY and not customer.lei_valid:
            factors.append(
                self._factor(
                    "missing_lei",
                    1.0,
                    weights["missing_lei"],
                    "No valid LEI was supplied; applicability must be confirmed for the customer type.",
                )
            )
        if (customer.aum_usd_millions or 0) >= self.policy.large_exposure_usd_millions:
            factors.append(
                self._factor(
                    "large_exposure",
                    1.0,
                    weights["large_exposure"],
                    "Exposure exceeds the configured demonstration threshold.",
                )
            )

        preliminary_score = min(100.0, self.policy.base_score + sum(factor.contribution for factor in factors))
        preliminary_category = self._category(preliminary_score)
        review_period = self.policy.review_period_days[preliminary_category.value]
        today = as_of_date or date.today()
        review_overdue = customer.last_kyc_review is None or (today - customer.last_kyc_review).days > review_period
        if review_overdue:
            factors.append(
                self._factor(
                    "kyc_overdue",
                    1.0,
                    weights["kyc_overdue"],
                    "KYC review is missing or older than the period configured for the preliminary risk tier.",
                )
            )

        score = round(min(100.0, self.policy.base_score + sum(factor.contribution for factor in factors)), 1)
        category = self._category(score)
        final_period = self.policy.review_period_days[category.value]
        recommended = today if review_overdue else customer.last_kyc_review + timedelta(days=final_period)
        rationale = [factor.explanation for factor in factors]
        if not rationale:
            rationale = ["No configured risk factor was triggered beyond the policy base score."]
        return RiskAssessment(
            customer_record_id=customer.record_id,
            policy_version=self.policy.version,
            score=score,
            category=category,
            factors=factors,
            recommended_review_date=recommended,
            rationale=rationale,
        )
