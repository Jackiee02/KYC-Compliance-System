import json
from pathlib import Path

from kyc_platform.config import Settings
from kyc_platform.services.pipeline import PipelineService


def test_offline_pipeline_writes_auditable_artifacts(test_settings: Settings) -> None:
    result = PipelineService(test_settings).run(
        record_count=100,
        offline=True,
        duplicate_rate=0.05,
        sanctions_injection_rate=0.03,
        seed=11,
    )

    manifest_path = Path(result.manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["status"] == "completed"
    assert manifest["record_count"] == 105
    assert manifest["sanctions_version"] == "offline-fixture-v1"
    assert manifest["summary"]["potential_match_count"] >= 1
    assert manifest["summary"]["duplicate_candidate_count"] >= 1
    assert len(manifest["artifacts"]) == 6
    for artifact in manifest["artifacts"]:
        assert len(artifact["sha256"]) == 64
        assert (manifest_path.parent / artifact["path"]).exists()


def test_pipeline_rejects_invalid_record_count(test_settings: Settings) -> None:
    try:
        PipelineService(test_settings).run(record_count=0)
    except ValueError as exc:
        assert "record_count" in str(exc)
    else:
        raise AssertionError("pipeline should reject a non-positive record count")
