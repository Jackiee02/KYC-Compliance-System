import csv
import hashlib
import itertools
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from kyc_platform.domain.models import CustomerRecord, SanctionsDataset, SanctionsEntity
from kyc_platform.services.deduplication import EntityResolutionService
from kyc_platform.services.normalization import normalize_customer
from kyc_platform.services.reporting import sha256_file
from kyc_platform.services.risk import RiskEngine, RiskPolicy
from kyc_platform.services.sanctions import ScreeningEngine


class ScreeningLabel(BaseModel):
    record_id: str
    expected_entity_id: Optional[str] = None
    expected_match: bool
    segment: str
    notes: str = ""


class RiskLabel(BaseModel):
    record_id: str
    expected_category: str
    scenario: str


class DuplicateLabel(BaseModel):
    record_id: str
    cluster_id: str
    scenario: str


class BinaryMetrics(BaseModel):
    sample_count: int
    positive_count: int
    negative_count: int
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    f1: float = Field(ge=0, le=1)
    accuracy: float = Field(ge=0, le=1)


class ScreeningMetrics(BaseModel):
    alerts: BinaryMetrics
    entity_recall_at_k: float = Field(ge=0, le=1)
    top1_entity_accuracy: float = Field(ge=0, le=1)
    entity_hit_count: int
    top1_correct_count: int


class SegmentMetric(BaseModel):
    segment: str
    metrics: BinaryMetrics


class ThresholdMetric(BaseModel):
    threshold: float
    precision: float
    recall: float
    f1: float
    false_positive: int
    false_negative: int


class RiskMetrics(BaseModel):
    sample_count: int
    correct_count: int
    accuracy: float = Field(ge=0, le=1)
    confusion_matrix: dict[str, dict[str, int]]


class EvaluationArtifact(BaseModel):
    path: str
    sha256: str
    row_count: Optional[int] = None


class BenchmarkEvaluationResult(BaseModel):
    run_id: str
    dataset_name: str
    dataset_version: str
    dataset_sha256: str
    policy_version: str
    as_of_date: date
    evaluated_at: datetime
    review_threshold: float
    match_threshold: float
    customer_count: int
    screening: ScreeningMetrics
    screening_segments: list[SegmentMetric]
    threshold_sweep: list[ThresholdMetric]
    risk: RiskMetrics
    duplicates: BinaryMetrics
    output_directory: str
    artifacts: list[EvaluationArtifact]


class BenchmarkDataset:
    def __init__(
        self,
        name: str,
        version: str,
        risk_policy_version: str,
        as_of_date: date,
        fingerprint: str,
        customers: dict[str, CustomerRecord],
        sanctions: SanctionsDataset,
        screening_labels: list[ScreeningLabel],
        risk_labels: list[RiskLabel],
        duplicate_labels: list[DuplicateLabel],
    ) -> None:
        self.name = name
        self.version = version
        self.risk_policy_version = risk_policy_version
        self.as_of_date = as_of_date
        self.fingerprint = fingerprint
        self.customers = customers
        self.sanctions = sanctions
        self.screening_labels = screening_labels
        self.risk_labels = risk_labels
        self.duplicate_labels = duplicate_labels

    @staticmethod
    def _read_csv(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def _optional(value: Optional[str]) -> Optional[str]:
        stripped = (value or "").strip()
        return stripped or None

    @classmethod
    def load(cls, root: Path) -> "BenchmarkDataset":
        root = root.resolve()
        manifest_path = root / "dataset.json"
        if not manifest_path.is_file():
            raise ValueError(f"benchmark manifest not found: {manifest_path}")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest["files"]
        required_paths = {name: root / relative for name, relative in files.items()}
        missing = [str(path) for path in required_paths.values() if not path.is_file()]
        if missing:
            raise ValueError(f"benchmark files are missing: {', '.join(missing)}")

        digest = hashlib.sha256()
        for path in sorted([manifest_path, *required_paths.values()], key=lambda item: item.name):
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())

        customers: dict[str, CustomerRecord] = {}
        for row in cls._read_csv(required_paths["customers"]):
            record_id = row["record_id"].strip()
            if record_id in customers:
                raise ValueError(f"duplicate benchmark record_id: {record_id}")
            customers[record_id] = CustomerRecord(
                record_id=record_id,
                entity_type=row["entity_type"],
                legal_name=row["legal_name"],
                aliases=[alias.strip() for alias in row.get("aliases", "").split("|") if alias.strip()],
                registered_country=cls._optional(row.get("registered_country")),
                registration_number=cls._optional(row.get("registration_number")),
                lei=cls._optional(row.get("lei")),
                last_kyc_review=cls._optional(row.get("last_kyc_review")),
                aum_usd_millions=float(row["aum_usd_millions"]) if row.get("aum_usd_millions") else None,
                is_pep=row.get("is_pep", "false").strip().lower() == "true",
                source=row.get("source") or "benchmark",
            )

        sanctions_path = required_paths["sanctions"]
        entities = [
            SanctionsEntity.model_validate_json(line)
            for line in sanctions_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not entities:
            raise ValueError("benchmark sanctions list is empty")
        sanctions = SanctionsDataset(
            source="SYNTHETIC-GOLDEN-LIST",
            version=manifest["version"],
            content_sha256=sha256_file(sanctions_path),
            entities=entities,
        )
        screening_labels = [
            ScreeningLabel.model_validate(row) for row in cls._read_csv(required_paths["screening_labels"])
        ]
        risk_labels = [RiskLabel.model_validate(row) for row in cls._read_csv(required_paths["risk_labels"])]
        duplicate_labels = [
            DuplicateLabel.model_validate(row) for row in cls._read_csv(required_paths["duplicate_labels"])
        ]

        referenced = {
            *(label.record_id for label in screening_labels),
            *(label.record_id for label in risk_labels),
            *(label.record_id for label in duplicate_labels),
        }
        unknown = sorted(referenced - customers.keys())
        if unknown:
            raise ValueError(f"labels reference unknown customer records: {', '.join(unknown)}")
        invalid_labels = [
            label.record_id for label in screening_labels if label.expected_match != bool(label.expected_entity_id)
        ]
        if invalid_labels:
            raise ValueError(f"inconsistent screening labels: {', '.join(invalid_labels)}")

        return cls(
            name=manifest["name"],
            version=manifest["version"],
            risk_policy_version=manifest["risk_policy_version"],
            as_of_date=date.fromisoformat(manifest["as_of_date"]),
            fingerprint=digest.hexdigest(),
            customers=customers,
            sanctions=sanctions,
            screening_labels=screening_labels,
            risk_labels=risk_labels,
            duplicate_labels=duplicate_labels,
        )


def _safe_divide(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _binary_metrics(outcomes: list[tuple[bool, bool]]) -> BinaryMetrics:
    true_positive = sum(expected and predicted for expected, predicted in outcomes)
    false_positive = sum(not expected and predicted for expected, predicted in outcomes)
    true_negative = sum(not expected and not predicted for expected, predicted in outcomes)
    false_negative = sum(expected and not predicted for expected, predicted in outcomes)
    precision = _safe_divide(true_positive, true_positive + false_positive)
    recall = _safe_divide(true_positive, true_positive + false_negative)
    f1 = round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0
    return BinaryMetrics(
        sample_count=len(outcomes),
        positive_count=sum(expected for expected, _ in outcomes),
        negative_count=sum(not expected for expected, _ in outcomes),
        true_positive=true_positive,
        false_positive=false_positive,
        true_negative=true_negative,
        false_negative=false_negative,
        precision=precision,
        recall=recall,
        f1=f1,
        accuracy=_safe_divide(true_positive + true_negative, len(outcomes)),
    )


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


class BenchmarkEvaluationService:
    DEFAULT_THRESHOLDS = (0.60, 0.65, 0.70, 0.72, 0.75, 0.80, 0.86, 0.90, 0.95)

    def __init__(
        self,
        dataset_path: Path,
        policy: RiskPolicy,
        review_threshold: float = 0.72,
        match_threshold: float = 0.86,
        output_root: Optional[Path] = None,
    ) -> None:
        self.dataset_path = dataset_path
        self.policy = policy
        self.review_threshold = review_threshold
        self.match_threshold = match_threshold
        self.output_root = output_root

    def _screening_evaluation(
        self,
        dataset: BenchmarkDataset,
        engine: ScreeningEngine,
    ) -> tuple[ScreeningMetrics, list[SegmentMetric], list[dict[str, Any]]]:
        outcomes: list[tuple[bool, bool]] = []
        segment_outcomes: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
        records: list[dict[str, Any]] = []
        entity_hits = 0
        top1_correct = 0
        positive_count = sum(label.expected_match for label in dataset.screening_labels)
        for label in dataset.screening_labels:
            customer = normalize_customer(dataset.customers[label.record_id])
            result = engine.screen(customer)
            predicted = bool(result.matches)
            outcomes.append((label.expected_match, predicted))
            segment_outcomes[label.segment].append((label.expected_match, predicted))
            predicted_ids = [match.entity_id for match in result.matches]
            entity_hit = bool(label.expected_entity_id and label.expected_entity_id in predicted_ids)
            top1_hit = bool(label.expected_entity_id and predicted_ids and label.expected_entity_id == predicted_ids[0])
            entity_hits += entity_hit
            top1_correct += top1_hit
            if label.expected_match and not predicted:
                outcome = "false_negative"
            elif not label.expected_match and predicted:
                outcome = "false_positive"
            elif label.expected_match and not entity_hit:
                outcome = "wrong_entity"
            else:
                outcome = "correct"
            records.append(
                {
                    "record_id": label.record_id,
                    "legal_name": customer.legal_name,
                    "segment": label.segment,
                    "expected_match": label.expected_match,
                    "expected_entity_id": label.expected_entity_id or "",
                    "predicted_match": predicted,
                    "predicted_entity_ids": "|".join(predicted_ids),
                    "top_score": round(result.top_score, 4),
                    "outcome": outcome,
                    "notes": label.notes,
                }
            )
        metrics = ScreeningMetrics(
            alerts=_binary_metrics(outcomes),
            entity_recall_at_k=_safe_divide(entity_hits, positive_count),
            top1_entity_accuracy=_safe_divide(top1_correct, positive_count),
            entity_hit_count=entity_hits,
            top1_correct_count=top1_correct,
        )
        segments = [
            SegmentMetric(segment=segment, metrics=_binary_metrics(values))
            for segment, values in sorted(segment_outcomes.items())
        ]
        return metrics, segments, records

    def _threshold_sweep(self, dataset: BenchmarkDataset) -> list[ThresholdMetric]:
        sweep: list[ThresholdMetric] = []
        for threshold in self.DEFAULT_THRESHOLDS:
            engine = ScreeningEngine(
                dataset.sanctions,
                review_threshold=threshold,
                match_threshold=max(threshold, self.match_threshold),
            )
            outcomes = []
            for label in dataset.screening_labels:
                result = engine.screen(normalize_customer(dataset.customers[label.record_id]))
                outcomes.append((label.expected_match, bool(result.matches)))
            metrics = _binary_metrics(outcomes)
            sweep.append(
                ThresholdMetric(
                    threshold=threshold,
                    precision=metrics.precision,
                    recall=metrics.recall,
                    f1=metrics.f1,
                    false_positive=metrics.false_positive,
                    false_negative=metrics.false_negative,
                )
            )
        return sweep

    def _risk_evaluation(
        self,
        dataset: BenchmarkDataset,
        screening_engine: ScreeningEngine,
    ) -> tuple[RiskMetrics, list[dict[str, Any]]]:
        risk_engine = RiskEngine(self.policy)
        confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        records: list[dict[str, Any]] = []
        correct = 0
        for label in dataset.risk_labels:
            customer = normalize_customer(dataset.customers[label.record_id])
            screening = screening_engine.screen(customer)
            assessment = risk_engine.assess(customer, screening, as_of_date=dataset.as_of_date)
            predicted = assessment.category.value
            confusion[label.expected_category][predicted] += 1
            is_correct = predicted == label.expected_category
            correct += is_correct
            records.append(
                {
                    "record_id": label.record_id,
                    "legal_name": customer.legal_name,
                    "scenario": label.scenario,
                    "expected_category": label.expected_category,
                    "predicted_category": predicted,
                    "score": assessment.score,
                    "correct": is_correct,
                    "factors": "|".join(factor.code for factor in assessment.factors),
                }
            )
        normalized_confusion = {expected: dict(predicted) for expected, predicted in sorted(confusion.items())}
        return (
            RiskMetrics(
                sample_count=len(records),
                correct_count=correct,
                accuracy=_safe_divide(correct, len(records)),
                confusion_matrix=normalized_confusion,
            ),
            records,
        )

    @staticmethod
    def _duplicate_evaluation(
        dataset: BenchmarkDataset,
    ) -> tuple[BinaryMetrics, list[dict[str, Any]]]:
        labeled_ids = {label.record_id for label in dataset.duplicate_labels}
        customers = [normalize_customer(dataset.customers[record_id]) for record_id in sorted(labeled_ids)]
        predicted = EntityResolutionService().find_candidates(customers)
        predicted_pairs = {
            tuple(sorted((candidate.left_record_id, candidate.right_record_id))): candidate for candidate in predicted
        }
        clusters = {label.record_id: label.cluster_id for label in dataset.duplicate_labels}
        outcomes: list[tuple[bool, bool]] = []
        error_rows: list[dict[str, Any]] = []
        for left, right in itertools.combinations(sorted(labeled_ids), 2):
            expected = clusters[left] == clusters[right]
            pair = (left, right)
            is_predicted = pair in predicted_pairs
            outcomes.append((expected, is_predicted))
            if expected != is_predicted:
                candidate = predicted_pairs.get(pair)
                error_rows.append(
                    {
                        "left_record_id": left,
                        "right_record_id": right,
                        "expected_duplicate": expected,
                        "predicted_duplicate": is_predicted,
                        "score": candidate.score if candidate else "",
                        "outcome": "false_negative" if expected else "false_positive",
                    }
                )
        return _binary_metrics(outcomes), error_rows

    def run(self, output_root: Optional[Path] = None) -> BenchmarkEvaluationResult:
        dataset = BenchmarkDataset.load(self.dataset_path)
        if dataset.risk_policy_version != self.policy.version:
            raise ValueError(
                f"benchmark expects risk policy {dataset.risk_policy_version}, loaded policy is {self.policy.version}"
            )
        run_id = str(uuid4())
        artifact_root = output_root or self.output_root
        if artifact_root is None:
            raise ValueError("an evaluation output root is required")
        output_directory = artifact_root / "evaluations" / run_id
        output_directory.mkdir(parents=True, exist_ok=False)
        screening_engine = ScreeningEngine(
            dataset.sanctions,
            review_threshold=self.review_threshold,
            match_threshold=self.match_threshold,
        )
        screening, segments, screening_rows = self._screening_evaluation(dataset, screening_engine)
        sweep = self._threshold_sweep(dataset)
        risk, risk_rows = self._risk_evaluation(dataset, screening_engine)
        duplicates, duplicate_errors = self._duplicate_evaluation(dataset)

        screening_path = output_directory / "screening-records.csv"
        _write_csv(
            screening_path,
            [
                "record_id",
                "legal_name",
                "segment",
                "expected_match",
                "expected_entity_id",
                "predicted_match",
                "predicted_entity_ids",
                "top_score",
                "outcome",
                "notes",
            ],
            screening_rows,
        )
        sweep_path = output_directory / "threshold-sweep.csv"
        sweep_rows = [metric.model_dump() for metric in sweep]
        _write_csv(sweep_path, list(ThresholdMetric.model_fields), sweep_rows)
        risk_path = output_directory / "risk-records.csv"
        _write_csv(
            risk_path,
            [
                "record_id",
                "legal_name",
                "scenario",
                "expected_category",
                "predicted_category",
                "score",
                "correct",
                "factors",
            ],
            risk_rows,
        )
        duplicate_path = output_directory / "duplicate-errors.csv"
        _write_csv(
            duplicate_path,
            [
                "left_record_id",
                "right_record_id",
                "expected_duplicate",
                "predicted_duplicate",
                "score",
                "outcome",
            ],
            duplicate_errors,
        )
        artifacts = [
            EvaluationArtifact(path=path.name, sha256=sha256_file(path), row_count=row_count)
            for path, row_count in [
                (screening_path, len(screening_rows)),
                (sweep_path, len(sweep_rows)),
                (risk_path, len(risk_rows)),
                (duplicate_path, len(duplicate_errors)),
            ]
        ]
        result = BenchmarkEvaluationResult(
            run_id=run_id,
            dataset_name=dataset.name,
            dataset_version=dataset.version,
            dataset_sha256=dataset.fingerprint,
            policy_version=self.policy.version,
            as_of_date=dataset.as_of_date,
            evaluated_at=datetime.now(timezone.utc),
            review_threshold=self.review_threshold,
            match_threshold=self.match_threshold,
            customer_count=len(dataset.customers),
            screening=screening,
            screening_segments=segments,
            threshold_sweep=sweep,
            risk=risk,
            duplicates=duplicates,
            output_directory=str(output_directory),
            artifacts=artifacts,
        )
        summary_path = output_directory / "evaluation-summary.json"
        summary_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result
