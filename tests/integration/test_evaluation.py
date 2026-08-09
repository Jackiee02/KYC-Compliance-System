from kyc_platform.services.evaluation import BenchmarkDataset, BenchmarkEvaluationService
from kyc_platform.services.risk import RiskPolicy


def test_versioned_benchmark_dataset_is_well_formed(project_root) -> None:
    dataset = BenchmarkDataset.load(project_root / "datasets" / "benchmark-v1")

    assert dataset.name == "KYC Synthetic Golden Benchmark"
    assert dataset.version == "1.0.0"
    assert len(dataset.customers) == 66
    assert len(dataset.screening_labels) == 40
    assert sum(label.expected_match for label in dataset.screening_labels) == 24
    assert len(dataset.risk_labels) == 10
    assert len(dataset.duplicate_labels) == 16
    assert len(dataset.fingerprint) == 64


def test_benchmark_evaluation_exports_metrics_and_error_analysis(project_root, tmp_path) -> None:
    policy = RiskPolicy.load(project_root / "config" / "risk-policy.v1.json")
    service = BenchmarkEvaluationService(project_root / "datasets" / "benchmark-v1", policy)

    result = service.run(tmp_path)

    assert result.screening.alerts.precision == 0.75
    assert result.screening.alerts.recall == 1.0
    assert result.screening.alerts.f1 == 0.8571
    assert result.screening.entity_recall_at_k == 1.0
    assert result.risk.accuracy == 1.0
    assert result.duplicates.precision == 1.0
    assert result.duplicates.recall == 0.8333
    assert max(result.threshold_sweep, key=lambda metric: metric.f1).threshold == 0.95
    assert (tmp_path / "evaluations" / result.run_id / "evaluation-summary.json").is_file()
    assert {artifact.path for artifact in result.artifacts} == {
        "screening-records.csv",
        "threshold-sweep.csv",
        "risk-records.csv",
        "duplicate-errors.csv",
    }
