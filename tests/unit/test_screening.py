from kyc_platform.domain.models import CustomerRecord
from kyc_platform.services.normalization import normalize_customer
from kyc_platform.services.sanctions import (
    OFAC_SDN_URL,
    OFACSanctionsProvider,
    ScreeningEngine,
    offline_sanctions_dataset,
)


def test_exact_sanctions_name_is_a_potential_match() -> None:
    engine = ScreeningEngine(offline_sanctions_dataset())
    customer = normalize_customer(CustomerRecord(record_id="hit", legal_name="Central Bank of Iran"))

    result = engine.screen(customer)

    assert result.matches
    assert result.matches[0].decision == "potential_match"
    assert result.matches[0].score >= 0.99
    assert result.dataset_version == "offline-fixture-v1"


def test_unrelated_name_has_no_match() -> None:
    engine = ScreeningEngine(offline_sanctions_dataset())
    customer = normalize_customer(CustomerRecord(record_id="clear", legal_name="Sunny Flowers Limited"))

    result = engine.screen(customer)

    assert result.matches == []
    assert result.top_score == 0


def test_ofac_provider_parses_aliases_and_program_tags(tmp_path, monkeypatch) -> None:
    sdn = (
        b'4632,"BANK MARKAZI JOMHOURI ISLAMI IRAN","-0-","IRAN] [SDGT] [IRGC] [IFSR",'
        b'"-0-","-0-","-0-","-0-","-0-","-0-","-0-","test remarks"\n'
    )
    aliases = b'4632,1,"a.k.a.","CENTRAL BANK OF IRAN","-0-"\n'
    provider = OFACSanctionsProvider()
    monkeypatch.setattr(provider, "_download", lambda url: sdn if url == OFAC_SDN_URL else aliases)

    dataset = provider.fetch(tmp_path)

    assert len(dataset.entities) == 1
    assert dataset.entities[0].aliases == ["CENTRAL BANK OF IRAN"]
    assert dataset.entities[0].programs == ["IRAN", "SDGT", "IRGC", "IFSR"]
