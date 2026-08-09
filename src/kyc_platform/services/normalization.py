import random
import re
import unicodedata
from collections.abc import Iterable
from typing import Optional

from kyc_platform.domain.models import CustomerRecord, NormalizedCustomer

ENGLISH_LEGAL_SUFFIXES = {
    "CO",
    "COMPANY",
    "CORP",
    "CORPORATION",
    "GROUP",
    "HOLDING",
    "HOLDINGS",
    "INC",
    "INCORPORATED",
    "LIMITED",
    "LLC",
    "LTD",
    "PLC",
}
CHINESE_LEGAL_SUFFIXES = ("股份有限公司", "有限責任公司", "有限公司", "控股", "集團")


def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def split_name_variants(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"\s*(?:/|;|\||／)\s*", value)
    return list(dict.fromkeys(part.strip() for part in parts if part.strip()))


def normalize_name(value: str) -> str:
    if not value or not value.strip():
        return ""
    normalized = unicodedata.normalize("NFKC", value).upper()
    normalized = normalized.replace("&", " AND ").replace("@", " AT ")
    normalized = re.sub(r"[^0-9A-Z\u3400-\u9FFF\s]", " ", normalized)
    normalized = _collapse_spaces(normalized)

    suffix_removed = True
    while suffix_removed and normalized:
        suffix_removed = False
        for suffix in CHINESE_LEGAL_SUFFIXES:
            if normalized.endswith(suffix):
                normalized = normalized[: -len(suffix)].strip()
                suffix_removed = True
                break

    tokens = normalized.split()
    while tokens and tokens[-1] in ENGLISH_LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens) if tokens else normalized


def normalize_registration_number(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = unicodedata.normalize("NFKC", value).upper()
    normalized = re.sub(r"[^0-9A-Z]", "", normalized)
    return normalized or None


def validate_lei(value: Optional[str]) -> bool:
    if not value:
        return False
    lei = value.strip().upper()
    if not re.fullmatch(r"[0-9A-Z]{20}", lei):
        return False
    converted = "".join(character if character.isdigit() else str(ord(character) - 55) for character in lei)
    remainder = 0
    for character in converted:
        remainder = (remainder * 10 + int(character)) % 97
    return remainder == 1


def generate_valid_lei(prefix: str = "529900", rng: Optional[random.Random] = None) -> str:
    generator = rng or random.Random()
    if not re.fullmatch(r"[0-9A-Z]{4,18}", prefix.upper()):
        raise ValueError("LEI prefix must contain 4 to 18 uppercase letters or digits")
    body = prefix.upper() + "".join(generator.choices("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=18 - len(prefix)))
    numeric = "".join(character if character.isdigit() else str(ord(character) - 55) for character in body) + "00"
    check_digits = 98 - (int(numeric) % 97)
    lei = f"{body}{check_digits:02d}"
    if not validate_lei(lei):
        raise RuntimeError("generated LEI did not pass ISO 17442 validation")
    return lei


def normalize_customer(customer: CustomerRecord) -> NormalizedCustomer:
    variants: Iterable[str] = [customer.legal_name, *customer.aliases]
    expanded = [part for value in variants for part in split_name_variants(value)]
    normalized_variants = list(dict.fromkeys(filter(None, (normalize_name(value) for value in expanded))))
    primary = normalize_name(
        split_name_variants(customer.legal_name)[0] if split_name_variants(customer.legal_name) else ""
    )
    aliases = [value for value in normalized_variants if value != primary]
    return NormalizedCustomer(
        **customer.model_dump(),
        normalized_name=primary,
        normalized_aliases=aliases,
        normalized_registration_number=normalize_registration_number(customer.registration_number),
        lei_valid=validate_lei(customer.lei),
    )
