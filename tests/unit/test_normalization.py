import random

import pytest

from kyc_platform.domain.models import CustomerRecord
from kyc_platform.services.normalization import (
    generate_valid_lei,
    normalize_customer,
    normalize_name,
    normalize_registration_number,
    validate_lei,
)


def test_normalize_english_and_chinese_company_suffixes() -> None:
    assert normalize_name("Acme Holdings Limited") == "ACME"
    assert normalize_name("滙豐控股有限公司") == "滙豐"


def test_normalize_customer_preserves_original_and_expands_bilingual_names() -> None:
    customer = CustomerRecord(
        record_id="one",
        legal_name="HSBC HOLDINGS PLC / 滙豐控股有限公司",
        aliases=["Hongkong and Shanghai Banking Corporation Ltd"],
        registration_number=" HK- 001 23 ",
    )

    normalized = normalize_customer(customer)

    assert normalized.legal_name == customer.legal_name
    assert normalized.normalized_name == "HSBC"
    assert "滙豐" in normalized.normalized_aliases
    assert normalized.normalized_registration_number == "HK00123"


def test_generate_and_validate_iso_17442_lei() -> None:
    lei = generate_valid_lei(rng=random.Random(7))

    assert len(lei) == 20
    assert validate_lei(lei)


@pytest.mark.parametrize("value", [None, "", "123", "529900INVALID0000000"])
def test_reject_invalid_lei(value: str) -> None:
    assert not validate_lei(value)


def test_empty_registration_number_normalizes_to_none() -> None:
    assert normalize_registration_number(" -- ") is None
