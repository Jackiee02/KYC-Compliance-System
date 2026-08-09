import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Optional

from kyc_platform.config import get_settings
from kyc_platform.domain.models import CustomerRecord
from kyc_platform.infrastructure.database import Database
from kyc_platform.logging import configure_logging
from kyc_platform.services.evaluation import BenchmarkEvaluationService
from kyc_platform.services.normalization import normalize_customer
from kyc_platform.services.pipeline import PipelineService
from kyc_platform.services.risk import RiskPolicy
from kyc_platform.services.sanctions import OFACSanctionsProvider, ScreeningEngine, offline_sanctions_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kyc", description="KYC Compliance Platform command line interface")
    subparsers = parser.add_subparsers(dest="command", required=True)

    pipeline = subparsers.add_parser("pipeline", help="Run the synthetic KYC pipeline")
    pipeline.add_argument("--records", type=int, default=100)
    pipeline.add_argument("--duplicate-rate", type=float, default=0.03)
    pipeline.add_argument("--sanctions-injection-rate", type=float, default=0.005)
    pipeline.add_argument("--seed", type=int, default=2026)
    pipeline.add_argument("--offline", action=argparse.BooleanOptionalAction, default=None)
    pipeline.add_argument("--enrich-lei", action="store_true")
    pipeline.add_argument("--lei-limit", type=int, default=100)

    screen = subparsers.add_parser("screen", help="Screen one name against a sanctions dataset")
    screen.add_argument("name")
    screen.add_argument("--country")
    screen.add_argument("--offline", action=argparse.BooleanOptionalAction, default=None)

    subparsers.add_parser("db-init", help="Create database tables")

    evaluate = subparsers.add_parser("evaluate", help="Evaluate screening, risk, and deduplication benchmarks")
    evaluate.add_argument("--dataset", type=Path)
    evaluate.add_argument("--output-dir", type=Path)

    serve = subparsers.add_parser("serve", help="Run the FastAPI service")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_directories()

    if args.command == "pipeline":
        result = PipelineService(settings).run(
            record_count=args.records,
            offline=args.offline,
            duplicate_rate=args.duplicate_rate,
            sanctions_injection_rate=args.sanctions_injection_rate,
            seed=args.seed,
            enrich_lei=args.enrich_lei,
            lei_enrichment_limit=args.lei_limit,
        )
        print(result.model_dump_json(indent=2))
        return

    if args.command == "screen":
        use_offline = settings.offline if args.offline is None else args.offline
        dataset = (
            offline_sanctions_dataset()
            if use_offline
            else OFACSanctionsProvider(settings.external_request_timeout_seconds).fetch(settings.data_dir / "sanctions")
        )
        engine = ScreeningEngine(
            dataset,
            review_threshold=settings.sanctions_review_threshold,
            match_threshold=settings.sanctions_match_threshold,
        )
        customer = normalize_customer(
            CustomerRecord(legal_name=args.name, registered_country=args.country, source="cli")
        )
        print(engine.screen(customer).model_dump_json(indent=2))
        return

    if args.command == "db-init":
        database = Database(settings.database_url)
        database.create_schema()
        database.ping()
        print(f"Database initialized: {settings.database_url}")
        return

    if args.command == "evaluate":
        policy = RiskPolicy.load(settings.risk_policy_path)
        result = BenchmarkEvaluationService(
            dataset_path=args.dataset or settings.benchmark_dataset_path,
            policy=policy,
            review_threshold=settings.sanctions_review_threshold,
            match_threshold=settings.sanctions_match_threshold,
        ).run(args.output_dir or settings.output_dir)
        print(result.model_dump_json(indent=2))
        return

    if args.command == "serve":
        import uvicorn

        uvicorn.run("kyc_platform.api.app:app", host=args.host, port=args.port, reload=args.reload)
