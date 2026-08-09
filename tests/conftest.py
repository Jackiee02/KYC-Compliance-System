from pathlib import Path

import pytest

from kyc_platform.config import Settings


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def test_settings(tmp_path: Path, project_root: Path) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{(tmp_path / 'kyc-test.db').as_posix()}",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "outputs",
        offline=True,
        risk_policy_path=project_root / "config" / "risk-policy.v1.json",
    )
