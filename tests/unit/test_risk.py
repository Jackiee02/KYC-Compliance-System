from datetime import date
from pathlib import Path

from kyc_platform.domain.models import CustomerRecord, RiskCategory
from kyc_platform.services.normalization import generate_valid_lei, normalize_customer
from kyc_platform.services.risk import RiskEngine, RiskPolicy
from kyc_platform.services.sanctions import ScreeningEngine, offline_sanctions_dataset


def _engine(project_root: Path) -> RiskEngine:
    return RiskEngine(RiskPolicy.load(project_root / "config" / "risk-policy.v1.json"))


def test_sanctions_hit_is_explainable_and_high_priority(project_root: Path) -> None:
    customer = normalize_customer(CustomerRecord(record_id="hit", legal_name="Central Bank of Iran"))
    screening = ScreeningEngine(offline_sanctions_dataset()).screen(customer)

    assessment = _engine(project_root).assess(customer, screening)

    assert assessment.category == RiskCategory.CRITICAL
    assert any(factor.code == "sanctions_match" for factor in assessment.factors)
    assert assessment.policy_version == "2026.08-demo.1"


def test_low_risk_customer_with_current_review_stays_low(project_root: Path) -> None:
    customer = normalize_customer(
        CustomerRecord(
            record_id="low",
            legal_name="Sunny Flowers Limited",
            lei=generate_valid_lei(),
            last_kyc_review=date.today(),
            aum_usd_millions=10,
            registered_country="HK",
        )
    )
    screening = ScreeningEngine(offline_sanctions_dataset()).screen(customer)

    assessment = _engine(project_root).assess(customer, screening)

    assert assessment.category == RiskCategory.LOW
    assert assessment.score == 10
