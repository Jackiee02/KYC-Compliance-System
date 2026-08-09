import csv
import hashlib
import io
import json
import re
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import jellyfish
from rapidfuzz import fuzz, process

from kyc_platform.domain.models import (
    NormalizedCustomer,
    SanctionsDataset,
    SanctionsEntity,
    ScreeningMatch,
    ScreeningResult,
)
from kyc_platform.services.normalization import normalize_name

OFAC_SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.csv"
OFAC_ALIAS_URL = "https://www.treasury.gov/ofac/downloads/alt.csv"


def _dataset_hash(entities: Iterable[SanctionsEntity]) -> str:
    payload = [entity.model_dump(mode="json") for entity in entities]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def offline_sanctions_dataset() -> SanctionsDataset:
    entities = [
        SanctionsEntity(
            entity_id="OFFLINE-1",
            source="offline-fixture",
            primary_name="CENTRAL BANK OF IRAN",
            aliases=["BANK MARKAZI JOMHOURI ISLAMI IRAN"],
            entity_type="Entity",
            countries=["IR"],
            programs=["TEST-SANCTIONS"],
        ),
        SanctionsEntity(
            entity_id="OFFLINE-2",
            source="offline-fixture",
            primary_name="NORTH KOREA TRADING CORPORATION",
            aliases=["DPRK TRADING CORP"],
            entity_type="Entity",
            countries=["KP"],
            programs=["TEST-SANCTIONS"],
        ),
        SanctionsEntity(
            entity_id="OFFLINE-3",
            source="offline-fixture",
            primary_name="SYRIAN ARAB REPUBLIC BANK",
            aliases=["SYRIA NATIONAL BANK"],
            entity_type="Entity",
            countries=["SY"],
            programs=["TEST-SANCTIONS"],
        ),
    ]
    return SanctionsDataset(
        source="offline-fixture",
        version="offline-fixture-v1",
        content_sha256=_dataset_hash(entities),
        entities=entities,
    )


class OFACSanctionsProvider:
    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    def _download(self, url: str) -> bytes:
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.content

    @staticmethod
    def _decode(payload: bytes) -> str:
        for encoding in ("utf-8-sig", "latin-1"):
            try:
                return payload.decode(encoding)
            except UnicodeDecodeError:
                continue
        return payload.decode("utf-8", errors="replace")

    @staticmethod
    def _parse_programs(value: str) -> list[str]:
        return [program.strip(" []") for program in re.split(r"\]\s*\[|,", value) if program.strip(" []")]

    def fetch(self, snapshot_directory: Path) -> SanctionsDataset:
        snapshot_directory.mkdir(parents=True, exist_ok=True)
        sdn_payload = self._download(OFAC_SDN_URL)
        alias_payload = self._download(OFAC_ALIAS_URL)
        retrieved_at = datetime.now(timezone.utc)
        stamp = retrieved_at.strftime("%Y%m%dT%H%M%SZ")
        (snapshot_directory / f"ofac-sdn-{stamp}.csv").write_bytes(sdn_payload)
        (snapshot_directory / f"ofac-alias-{stamp}.csv").write_bytes(alias_payload)

        aliases: dict[str, list[str]] = {}
        for row in csv.reader(io.StringIO(self._decode(alias_payload))):
            if len(row) >= 4 and row[0].strip() and row[3].strip():
                aliases.setdefault(row[0].strip(), []).append(row[3].strip())

        entities: list[SanctionsEntity] = []
        for row in csv.reader(io.StringIO(self._decode(sdn_payload))):
            if len(row) < 4 or not row[0].strip() or not row[1].strip():
                continue
            entity_id = row[0].strip()
            entities.append(
                SanctionsEntity(
                    entity_id=entity_id,
                    source="OFAC-SDN",
                    primary_name=row[1].strip(),
                    aliases=aliases.get(entity_id, []),
                    entity_type=row[2].strip() or None,
                    programs=self._parse_programs(row[3]),
                    remarks=row[11].strip() if len(row) > 11 and row[11].strip() else None,
                )
            )

        if not entities:
            raise ValueError("OFAC source was downloaded but no sanctions entities could be parsed")
        combined_hash = hashlib.sha256(sdn_payload + alias_payload).hexdigest()
        return SanctionsDataset(
            source="OFAC-SDN",
            version=f"{stamp}-{combined_hash[:12]}",
            retrieved_at=retrieved_at,
            content_sha256=combined_hash,
            entities=entities,
        )


class ScreeningEngine:
    def __init__(
        self,
        dataset: SanctionsDataset,
        review_threshold: float = 0.72,
        match_threshold: float = 0.86,
    ) -> None:
        if review_threshold > match_threshold:
            raise ValueError("review threshold cannot exceed match threshold")
        self.dataset = dataset
        self.review_threshold = review_threshold
        self.match_threshold = match_threshold
        self._choices: list[str] = []
        self._choice_to_entities: dict[str, set[int]] = {}
        for index, entity in enumerate(dataset.entities):
            for name in [entity.primary_name, *entity.aliases]:
                normalized = normalize_name(name)
                if not normalized:
                    continue
                if normalized not in self._choice_to_entities:
                    self._choices.append(normalized)
                    self._choice_to_entities[normalized] = set()
                self._choice_to_entities[normalized].add(index)

    @staticmethod
    def _score(left: str, right: str) -> tuple[float, dict[str, float]]:
        weighted = fuzz.WRatio(left, right) / 100.0
        token_set = fuzz.token_set_ratio(left, right) / 100.0
        jaro = jellyfish.jaro_winkler_similarity(left, right)
        score = min(1.0, 0.45 * weighted + 0.35 * token_set + 0.20 * jaro)
        return score, {"weighted_ratio": weighted, "token_set_ratio": token_set, "jaro_winkler": jaro}

    def _candidate_entities(self, names: Sequence[str], limit: int = 30) -> set[int]:
        candidates: set[int] = set()
        for name in names:
            extracted = process.extract(
                name,
                self._choices,
                scorer=fuzz.WRatio,
                score_cutoff=max(35.0, self.review_threshold * 100 - 20),
                limit=limit,
            )
            for choice, _, _ in extracted:
                candidates.update(self._choice_to_entities[choice])
        return candidates

    def screen(self, customer: NormalizedCustomer, top_k: int = 5) -> ScreeningResult:
        customer_names = [customer.normalized_name, *customer.normalized_aliases]
        customer_names = [name for name in customer_names if name]
        matches: list[ScreeningMatch] = []
        for entity_index in self._candidate_entities(customer_names):
            entity = self.dataset.entities[entity_index]
            best: Optional[tuple[float, dict[str, float], str, str]] = None
            for customer_name in customer_names:
                for entity_name in [entity.primary_name, *entity.aliases]:
                    normalized_entity_name = normalize_name(entity_name)
                    score, components = self._score(customer_name, normalized_entity_name)
                    if best is None or score > best[0]:
                        best = (score, components, customer_name, entity_name)
            if best is None or best[0] < self.review_threshold:
                continue
            decision = "potential_match" if best[0] >= self.match_threshold else "review"
            matches.append(
                ScreeningMatch(
                    entity_id=entity.entity_id,
                    source=entity.source,
                    matched_name=best[3],
                    score=round(best[0], 4),
                    decision=decision,
                    components={key: round(value, 4) for key, value in best[1].items()},
                    programs=entity.programs,
                    evidence={"customer_normalized_name": best[2], "entity_primary_name": entity.primary_name},
                )
            )
        matches.sort(key=lambda match: match.score, reverse=True)
        return ScreeningResult(
            customer_record_id=customer.record_id,
            dataset_source=self.dataset.source,
            dataset_version=self.dataset.version,
            threshold=self.match_threshold,
            matches=matches[:top_k],
        )
