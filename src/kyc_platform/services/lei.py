import json
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel
from rapidfuzz import fuzz

from kyc_platform.services.normalization import normalize_name, validate_lei


class LEIMatch(BaseModel):
    lei: str
    legal_name: str
    score: float
    status: Optional[str] = None


class GLEIFClient:
    BASE_URL = "https://api.gleif.org/api/v1/lei-records"

    def __init__(self, cache_path: Path, timeout_seconds: float = 30.0) -> None:
        self.cache_path = cache_path
        self.timeout_seconds = timeout_seconds
        self.cache: dict[str, Optional[dict[str, object]]] = self._load_cache()

    def _load_cache(self) -> dict[str, Optional[dict[str, object]]]:
        if not self.cache_path.exists():
            return {}
        try:
            return json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.cache, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        temporary.replace(self.cache_path)

    def lookup(self, legal_name: str) -> Optional[LEIMatch]:
        key = normalize_name(legal_name)
        if key in self.cache:
            cached = self.cache[key]
            return LEIMatch.model_validate(cached) if cached else None

        params = {"filter[entity.legalName]": legal_name, "page[size]": 5}
        with httpx.Client(timeout=self.timeout_seconds, follow_redirects=True) as client:
            response = client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            records: list[dict[str, object]] = response.json().get("data", [])

        best: Optional[LEIMatch] = None
        for record in records:
            attributes = record.get("attributes", {})
            if not isinstance(attributes, dict):
                continue
            lei = str(attributes.get("lei", ""))
            entity = attributes.get("entity", {})
            if not isinstance(entity, dict):
                continue
            name_data = entity.get("legalName", {})
            candidate_name = name_data.get("name", "") if isinstance(name_data, dict) else ""
            if not candidate_name or not validate_lei(lei):
                continue
            score = fuzz.WRatio(key, normalize_name(str(candidate_name))) / 100.0
            registration = entity.get("registrationStatus")
            candidate = LEIMatch(lei=lei, legal_name=str(candidate_name), score=score, status=str(registration or ""))
            if best is None or candidate.score > best.score:
                best = candidate

        self.cache[key] = best.model_dump(mode="json") if best else None
        self._save_cache()
        return best
