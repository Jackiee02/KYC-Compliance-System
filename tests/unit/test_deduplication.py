from kyc_platform.domain.models import CustomerRecord
from kyc_platform.services.deduplication import EntityResolutionService
from kyc_platform.services.normalization import normalize_customer


def test_duplicate_candidates_are_preserved_for_review() -> None:
    customers = [
        normalize_customer(
            CustomerRecord(
                record_id="left",
                legal_name="Acme Holdings Limited",
                registered_country="HK",
                registration_number="1234567",
            )
        ),
        normalize_customer(
            CustomerRecord(
                record_id="right",
                legal_name=" acme holdings ltd ",
                registered_country="HK",
                registration_number="1234568",
            )
        ),
        normalize_customer(CustomerRecord(record_id="other", legal_name="Sunny Flowers Ltd", registered_country="HK")),
    ]

    candidates = EntityResolutionService().find_candidates(customers)

    assert len(candidates) == 1
    assert {candidates[0].left_record_id, candidates[0].right_record_id} == {"left", "right"}
    assert candidates[0].recommendation == "manual_review"
    assert len(customers) == 3
