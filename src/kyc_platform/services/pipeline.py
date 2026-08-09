import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import httpx

from kyc_platform.config import Settings
from kyc_platform.domain.models import (
    ArtifactRecord,
    CustomerRecord,
    NormalizedCustomer,
    PipelineManifest,
    PipelineRunResult,
)
from kyc_platform.services.deduplication import EntityResolutionService
from kyc_platform.services.generator import SyntheticCustomerGenerator
from kyc_platform.services.lei import GLEIFClient
from kyc_platform.services.normalization import normalize_customer
from kyc_platform.services.reporting import ReportWriter, build_summary, sha256_file
from kyc_platform.services.risk import RiskEngine, RiskPolicy
from kyc_platform.services.sanctions import OFACSanctionsProvider, ScreeningEngine, offline_sanctions_dataset

logger = logging.getLogger(__name__)


class PipelineService:
    def __init__(self, settings: Settings, policy: Optional[RiskPolicy] = None) -> None:
        self.settings = settings
        self.policy = policy or RiskPolicy.load(settings.risk_policy_path)

    def _enrich_lei(self, customers: list[CustomerRecord], limit: int) -> list[CustomerRecord]:
        client = GLEIFClient(
            cache_path=self.settings.data_dir / "cache" / "gleif.json",
            timeout_seconds=self.settings.external_request_timeout_seconds,
        )
        enriched: list[CustomerRecord] = []
        queried = 0
        for customer in customers:
            if customer.lei or queried >= limit:
                enriched.append(customer)
                continue
            queried += 1
            try:
                match = client.lookup(customer.legal_name)
            except httpx.HTTPError as exc:
                logger.warning("GLEIF lookup failed for %s: %s", customer.record_id, exc)
                match = None
            if match and match.score >= 0.80:
                customer = customer.model_copy(update={"lei": match.lei})
            enriched.append(customer)
        return enriched

    def run(
        self,
        record_count: int,
        offline: Optional[bool] = None,
        duplicate_rate: float = 0.03,
        sanctions_injection_rate: float = 0.005,
        seed: int = 2026,
        enrich_lei: bool = False,
        lei_enrichment_limit: int = 100,
    ) -> PipelineRunResult:
        if record_count <= 0:
            raise ValueError("record_count must be positive")
        if not 0 <= duplicate_rate <= 0.5:
            raise ValueError("duplicate_rate must be between 0 and 0.5")
        if not 0 <= sanctions_injection_rate <= 0.5:
            raise ValueError("sanctions_injection_rate must be between 0 and 0.5")

        self.settings.ensure_directories()
        run_id = str(uuid4())
        started_at = datetime.now(timezone.utc)
        run_directory = self.settings.output_dir / run_id
        run_directory.mkdir(parents=True, exist_ok=False)
        use_offline = self.settings.offline if offline is None else offline

        if use_offline:
            sanctions = offline_sanctions_dataset()
        else:
            sanctions = OFACSanctionsProvider(self.settings.external_request_timeout_seconds).fetch(
                self.settings.data_dir / "sanctions"
            )

        generator = SyntheticCustomerGenerator(seed=seed)
        source_customers = generator.generate(
            count=record_count,
            sanctions=sanctions,
            duplicate_rate=duplicate_rate,
            sanctions_injection_rate=sanctions_injection_rate,
        )
        if enrich_lei:
            if use_offline:
                raise ValueError("LEI enrichment cannot be enabled in offline mode")
            source_customers = self._enrich_lei(source_customers, lei_enrichment_limit)

        customers: list[NormalizedCustomer] = [normalize_customer(customer) for customer in source_customers]
        screening_engine = ScreeningEngine(
            sanctions,
            review_threshold=self.settings.sanctions_review_threshold,
            match_threshold=self.settings.sanctions_match_threshold,
        )
        screenings = [screening_engine.screen(customer) for customer in customers]
        risk_engine = RiskEngine(self.policy)
        assessments = [risk_engine.assess(customer, screening) for customer, screening in zip(customers, screenings)]
        duplicates = EntityResolutionService().find_candidates(customers)
        summary = build_summary(customers, screenings, assessments, duplicates)

        writer = ReportWriter(run_directory)
        artifacts = writer.write_all(customers, screenings, assessments, duplicates, summary)
        completed_at = datetime.now(timezone.utc)
        manifest = PipelineManifest(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            status="completed",
            record_count=len(customers),
            policy_version=self.policy.version,
            sanctions_source=sanctions.source,
            sanctions_version=sanctions.version,
            offline=use_offline,
            configuration={
                "requested_record_count": record_count,
                "duplicate_rate": duplicate_rate,
                "sanctions_injection_rate": sanctions_injection_rate,
                "seed": seed,
                "enrich_lei": enrich_lei,
                "lei_enrichment_limit": lei_enrichment_limit,
            },
            summary=summary,
            artifacts=artifacts,
        )
        manifest_path = run_directory / "manifest.json"
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        manifest_artifact = ArtifactRecord(
            path=manifest_path.name,
            sha256=sha256_file(manifest_path),
            media_type="application/json",
        )
        logger.info(
            "pipeline completed",
            extra={"run_id": run_id, "event_type": "pipeline_completed", "artifact_count": len(artifacts) + 1},
        )
        return PipelineRunResult(
            run_id=run_id,
            output_directory=str(run_directory),
            manifest_path=str(manifest_path),
            summary={**summary, "manifest_sha256": manifest_artifact.sha256},
        )
