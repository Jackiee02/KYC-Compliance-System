from fastapi import APIRouter, Depends, Query

from kyc_platform.api.dependencies import get_evaluation_service
from kyc_platform.services.evaluation import BenchmarkDataset, BenchmarkEvaluationResult, BenchmarkEvaluationService

router = APIRouter(prefix="/api/v1/evaluations", tags=["evaluations"])


@router.get("/benchmark/info")
def benchmark_info(
    service: BenchmarkEvaluationService = Depends(get_evaluation_service),
) -> dict[str, object]:
    dataset = BenchmarkDataset.load(service.dataset_path)
    return {
        "name": dataset.name,
        "version": dataset.version,
        "sha256": dataset.fingerprint,
        "customer_count": len(dataset.customers),
        "screening_label_count": len(dataset.screening_labels),
        "screening_positive_count": sum(label.expected_match for label in dataset.screening_labels),
        "risk_label_count": len(dataset.risk_labels),
        "duplicate_record_count": len(dataset.duplicate_labels),
        "synthetic": True,
    }


@router.get("/benchmark/runs", response_model=list[BenchmarkEvaluationResult])
def list_benchmark_runs(
    limit: int = Query(default=10, ge=1, le=100),
    service: BenchmarkEvaluationService = Depends(get_evaluation_service),
) -> list[BenchmarkEvaluationResult]:
    return _list_results(service, limit)


def _list_results(service: BenchmarkEvaluationService, limit: int) -> list[BenchmarkEvaluationResult]:
    if service.output_root is None:
        return []
    results_root = service.output_root / "evaluations"
    if not results_root.exists():
        return []
    paths = sorted(results_root.glob("*/evaluation-summary.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    results: list[BenchmarkEvaluationResult] = []
    for path in paths[:limit]:
        try:
            results.append(BenchmarkEvaluationResult.model_validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return results


@router.post("/benchmark/runs", response_model=BenchmarkEvaluationResult)
def run_benchmark(
    service: BenchmarkEvaluationService = Depends(get_evaluation_service),
) -> BenchmarkEvaluationResult:
    return service.run()
