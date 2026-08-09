import hashlib
import json
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from kyc_platform.domain.models import (
    ArtifactRecord,
    DuplicateCandidate,
    NormalizedCustomer,
    RiskAssessment,
    ScreeningResult,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _temporary_path(path: Path) -> Path:
    return path.with_name(f".{path.stem}.tmp{path.suffix}")


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    temporary = _temporary_path(path)
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(path)


class ReportWriter:
    def __init__(self, output_directory: Path) -> None:
        self.output_directory = output_directory
        self.output_directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _customer_rows(
        customers: Sequence[NormalizedCustomer],
        screenings: Sequence[ScreeningResult],
        assessments: Sequence[RiskAssessment],
    ) -> list[dict[str, Any]]:
        screening_by_id = {result.customer_record_id: result for result in screenings}
        risk_by_id = {assessment.customer_record_id: assessment for assessment in assessments}
        rows: list[dict[str, Any]] = []
        for customer in customers:
            screening = screening_by_id[customer.record_id]
            risk = risk_by_id[customer.record_id]
            rows.append(
                {
                    "record_id": customer.record_id,
                    "entity_type": customer.entity_type.value,
                    "legal_name": customer.legal_name,
                    "normalized_name": customer.normalized_name,
                    "registered_country": customer.registered_country,
                    "registration_number": customer.registration_number,
                    "lei": customer.lei,
                    "lei_valid": customer.lei_valid,
                    "last_kyc_review": customer.last_kyc_review,
                    "sanctions_top_score": screening.top_score,
                    "sanctions_match_count": len(screening.matches),
                    "risk_score": risk.score,
                    "risk_category": risk.category.value,
                    "recommended_review_date": risk.recommended_review_date,
                    "source": customer.source,
                    "source_reference": customer.source_reference,
                }
            )
        return rows

    def write_all(
        self,
        customers: Sequence[NormalizedCustomer],
        screenings: Sequence[ScreeningResult],
        assessments: Sequence[RiskAssessment],
        duplicates: Sequence[DuplicateCandidate],
        summary: dict[str, Any],
    ) -> list[ArtifactRecord]:
        artifacts: list[ArtifactRecord] = []
        customer_rows = self._customer_rows(customers, screenings, assessments)

        customers_path = self.output_directory / "customers.csv"
        pd.DataFrame(customer_rows).to_csv(customers_path, index=False, encoding="utf-8-sig")
        artifacts.append(self._artifact(customers_path, "text/csv", len(customer_rows)))

        screenings_path = self.output_directory / "screening-results.jsonl"
        _write_jsonl(screenings_path, (result.model_dump(mode="json") for result in screenings))
        artifacts.append(self._artifact(screenings_path, "application/x-ndjson", len(screenings)))

        risk_path = self.output_directory / "risk-assessments.jsonl"
        _write_jsonl(risk_path, (assessment.model_dump(mode="json") for assessment in assessments))
        artifacts.append(self._artifact(risk_path, "application/x-ndjson", len(assessments)))

        duplicate_rows = [candidate.model_dump(mode="json") for candidate in duplicates]
        duplicates_path = self.output_directory / "duplicate-candidates.csv"
        duplicate_columns = ["left_record_id", "right_record_id", "score", "components", "recommendation"]
        pd.DataFrame(duplicate_rows, columns=duplicate_columns).to_csv(
            duplicates_path, index=False, encoding="utf-8-sig"
        )
        artifacts.append(self._artifact(duplicates_path, "text/csv", len(duplicate_rows)))

        excel_path = self.output_directory / "kyc-compliance-report.xlsx"
        self._write_excel(excel_path, customer_rows, screenings, duplicate_rows, summary)
        artifacts.append(
            self._artifact(excel_path, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        )

        pdf_path = self.output_directory / "kyc-compliance-summary.pdf"
        self._write_pdf(pdf_path, summary)
        artifacts.append(self._artifact(pdf_path, "application/pdf"))
        return artifacts

    @staticmethod
    def _artifact(path: Path, media_type: str, row_count: Optional[int] = None) -> ArtifactRecord:
        return ArtifactRecord(path=path.name, sha256=sha256_file(path), media_type=media_type, row_count=row_count)

    @staticmethod
    def _write_excel(
        path: Path,
        customer_rows: list[dict[str, Any]],
        screenings: Sequence[ScreeningResult],
        duplicate_rows: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> None:
        temporary = _temporary_path(path)
        match_rows = [
            {
                "record_id": screening.customer_record_id,
                **match.model_dump(mode="json"),
                "dataset_version": screening.dataset_version,
            }
            for screening in screenings
            for match in screening.matches
        ]
        with pd.ExcelWriter(temporary, engine="openpyxl") as writer:
            pd.DataFrame(customer_rows).to_excel(writer, sheet_name="Customers", index=False)
            pd.DataFrame(match_rows).to_excel(writer, sheet_name="Screening Matches", index=False)
            pd.DataFrame(duplicate_rows).to_excel(writer, sheet_name="Duplicate Candidates", index=False)
            pd.DataFrame(
                [
                    {"metric": key, "value": json.dumps(value) if isinstance(value, dict) else value}
                    for key, value in summary.items()
                ]
            ).to_excel(writer, sheet_name="Summary", index=False)
        temporary.replace(path)

    @staticmethod
    def _write_pdf(path: Path, summary: dict[str, Any]) -> None:
        temporary = _temporary_path(path)
        styles = getSampleStyleSheet()
        story = [Paragraph("KYC Compliance Pipeline Summary", styles["Title"]), Spacer(1, 12)]
        paragraphs = [
            f"Records processed: {summary['record_count']}.",
            f"Potential sanctions matches: {summary['potential_match_count']}.",
            f"Screening results requiring review: {summary['screening_review_count']}.",
            f"Duplicate candidates preserved for manual review: {summary['duplicate_candidate_count']}.",
            f"Risk distribution: {json.dumps(summary['risk_distribution'], sort_keys=True)}.",
            "Automated scores are decision support only and must not be treated as a legal or regulatory "
            "determination.",
        ]
        for text in paragraphs:
            story.extend([Paragraph(text, styles["BodyText"]), Spacer(1, 8)])
        SimpleDocTemplate(str(temporary), pagesize=letter).build(story)
        temporary.replace(path)


def build_summary(
    customers: Sequence[NormalizedCustomer],
    screenings: Sequence[ScreeningResult],
    assessments: Sequence[RiskAssessment],
    duplicates: Sequence[DuplicateCandidate],
) -> dict[str, Any]:
    risk_distribution = Counter(assessment.category.value for assessment in assessments)
    return {
        "record_count": len(customers),
        "valid_lei_count": sum(customer.lei_valid for customer in customers),
        "screening_review_count": sum(bool(result.matches) for result in screenings),
        "potential_match_count": sum(
            any(match.decision == "potential_match" for match in result.matches) for result in screenings
        ),
        "duplicate_candidate_count": len(duplicates),
        "risk_distribution": dict(sorted(risk_distribution.items())),
    }
