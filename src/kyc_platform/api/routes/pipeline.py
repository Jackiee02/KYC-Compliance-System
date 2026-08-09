from fastapi import APIRouter, Depends, HTTPException, Query, status

from kyc_platform.api.dependencies import get_pipeline_service
from kyc_platform.api.schemas import PipelineRunRequest, PipelineRunResponse
from kyc_platform.domain.models import PipelineManifest
from kyc_platform.services.pipeline import PipelineService

router = APIRouter(prefix="/api/v1/pipeline-runs", tags=["pipelines"])


def _load_manifest(service: PipelineService, run_id: str) -> PipelineManifest:
    output_root = service.settings.output_dir.resolve()
    manifest_path = (output_root / run_id / "manifest.json").resolve()
    if output_root not in manifest_path.parents or not manifest_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline run not found")
    return PipelineManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))


@router.get("", response_model=list[PipelineManifest])
def list_pipeline_runs(
    limit: int = Query(default=20, ge=1, le=100),
    service: PipelineService = Depends(get_pipeline_service),
) -> list[PipelineManifest]:
    output_root = service.settings.output_dir
    if not output_root.exists():
        return []
    manifests = sorted(output_root.glob("*/manifest.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    results: list[PipelineManifest] = []
    for path in manifests:
        try:
            results.append(PipelineManifest.model_validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
        if len(results) >= limit:
            break
    return results


@router.get("/{run_id}", response_model=PipelineManifest)
def get_pipeline_run(
    run_id: str,
    service: PipelineService = Depends(get_pipeline_service),
) -> PipelineManifest:
    return _load_manifest(service, run_id)


@router.post("", response_model=PipelineRunResponse)
def run_pipeline(
    payload: PipelineRunRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> PipelineRunResponse:
    result = service.run(
        record_count=payload.record_count,
        offline=payload.offline,
        duplicate_rate=payload.duplicate_rate,
        sanctions_injection_rate=payload.sanctions_injection_rate,
        seed=payload.seed,
    )
    return PipelineRunResponse.model_validate(result.model_dump())
