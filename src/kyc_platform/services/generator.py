import random
from datetime import date, timedelta

import numpy as np
from faker import Faker

from kyc_platform.domain.models import CustomerRecord, SanctionsDataset
from kyc_platform.services.normalization import generate_valid_lei


class SyntheticCustomerGenerator:
    """Deterministic synthetic data for development and model evaluation only."""

    COMPANY_PAIRS = [
        ("HSBC HOLDINGS PLC", "滙豐控股有限公司"),
        ("STANDARD CHARTERED PLC", "渣打集團有限公司"),
        ("BANK OF CHINA LIMITED", "中國銀行股份有限公司"),
        ("AIA GROUP LIMITED", "友邦保險控股有限公司"),
        ("HANG SENG BANK LIMITED", "恒生銀行有限公司"),
        ("TENCENT HOLDINGS LIMITED", "騰訊控股有限公司"),
    ]

    def __init__(self, seed: int = 2026) -> None:
        self.seed = seed
        self.random = random.Random(seed)
        self.numpy = np.random.default_rng(seed)
        Faker.seed(seed)
        self.fake = Faker("en_US")

    def _registration_number(self, country: str) -> str:
        if country == "HK":
            return str(self.random.randint(1_000_000, 19_999_999))
        return f"{country}{self.random.randint(100_000, 999_999)}"

    def generate(
        self,
        count: int,
        sanctions: SanctionsDataset,
        duplicate_rate: float = 0.03,
        sanctions_injection_rate: float = 0.005,
    ) -> list[CustomerRecord]:
        if count <= 0:
            raise ValueError("count must be positive")
        countries = ["HK", "VG", "KY", "CN", "SG"]
        weights = [0.50, 0.20, 0.15, 0.10, 0.05]
        sanction_count = min(len(sanctions.entities), max(0, int(count * sanctions_injection_rate)))
        sanction_indexes = set(self.random.sample(range(count), sanction_count)) if sanction_count else set()
        customers: list[CustomerRecord] = []

        for index in range(count):
            aliases: list[str] = []
            if index in sanction_indexes:
                entity = sanctions.entities[index % len(sanctions.entities)]
                legal_name = entity.primary_name
                aliases = entity.aliases[:2]
            elif index < int(count * 0.10):
                legal_name, chinese_name = self.random.choice(self.COMPANY_PAIRS)
                aliases = [chinese_name]
            else:
                legal_name = self.fake.company().replace(",", "")

            country = self.random.choices(countries, weights=weights, k=1)[0]
            last_review = date.today() - timedelta(days=int(min(self.numpy.exponential(400), 2500)))
            lei = generate_valid_lei(rng=self.random) if self.random.random() < 0.12 else None
            customers.append(
                CustomerRecord(
                    record_id=f"KYC{index + 1:07d}",
                    legal_name=legal_name,
                    aliases=aliases,
                    registered_country=country,
                    registration_number=self._registration_number(country),
                    lei=lei,
                    incorporation_date=self.fake.date_between_dates(date(1990, 1, 1), date(2025, 12, 31)),
                    last_kyc_review=last_review,
                    aum_usd_millions=round(float(min(self.numpy.lognormal(3.5, 1.5), 10_000)), 2),
                    source="synthetic",
                    extra_data={"synthetic": True},
                )
            )

        duplicate_count = max(0, int(count * duplicate_rate))
        for duplicate_index, original in enumerate(self.random.sample(customers, duplicate_count), start=1):
            noisy_name = f" {original.legal_name.lower()} "
            registration = original.registration_number
            if registration and self.random.random() < 0.35:
                registration = (
                    f"{registration[:-1]}{(int(registration[-1]) + 1) % 10}"
                    if registration[-1].isdigit()
                    else registration
                )
            customers.append(
                original.model_copy(
                    update={
                        "record_id": f"KYC-DUP-{duplicate_index:07d}",
                        "legal_name": noisy_name,
                        "registration_number": registration,
                        "source_reference": original.record_id,
                    }
                )
            )
        return customers
