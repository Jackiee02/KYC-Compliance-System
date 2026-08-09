from fastapi.testclient import TestClient

from kyc_platform.api.app import create_app


def test_health_customer_screening_and_risk_endpoints(test_settings) -> None:
    with TestClient(create_app(test_settings)) as client:
        live = client.get("/health/live")
        ready = client.get("/health/ready")
        created = client.post(
            "/api/v1/customers",
            headers={"X-Actor-ID": "analyst-1"},
            json={"record_id": "api-1", "legal_name": "Acme Limited", "registered_country": "HK"},
        )
        listed = client.get("/api/v1/customers")
        screening = client.post(
            "/api/v1/screenings",
            json={"customer": {"record_id": "api-hit", "legal_name": "Central Bank of Iran"}},
        )
        risk = client.post(
            "/api/v1/risk-assessments",
            json={"customer": {"record_id": "api-hit", "legal_name": "Central Bank of Iran"}},
        )

    assert live.status_code == 200
    assert ready.json()["sanctions_dataset_version"] == "offline-fixture-v1"
    assert created.status_code == 201
    assert created.json()["normalized_name"] == "ACME"
    assert len(listed.json()) == 1
    assert screening.json()["matches"][0]["decision"] == "potential_match"
    assert risk.json()["assessment"]["category"] == "critical"


def test_duplicate_customer_returns_conflict(test_settings) -> None:
    payload = {"record_id": "same", "legal_name": "Acme Limited"}
    with TestClient(create_app(test_settings)) as client:
        assert client.post("/api/v1/customers", json=payload).status_code == 201
        assert client.post("/api/v1/customers", json=payload).status_code == 409


def test_business_workbench_case_review_and_report_flow(test_settings) -> None:
    with TestClient(create_app(test_settings)) as client:
        workbench = client.get("/")
        stylesheet = client.get("/static/app.css")
        initial_dashboard = client.get("/api/v1/dashboard")

        customer = client.post(
            "/api/v1/customers",
            headers={"X-Actor-ID": "workbench-analyst-01"},
            json={
                "record_id": "workbench-hit-1",
                "legal_name": "Central Bank of Iran",
                "registered_country": "IR",
                "source": "business-workbench",
            },
        ).json()
        assessment = client.post(
            f"/api/v1/customers/{customer['id']}/assessment",
            headers={"X-Actor-ID": "workbench-analyst-01"},
        )
        cases = client.get("/api/v1/cases?status=open")
        case_id = cases.json()[0]["id"]
        decision = client.post(
            f"/api/v1/cases/{case_id}/decision",
            headers={"X-Actor-ID": "workbench-analyst-01"},
            json={"decision": "escalate", "notes": "Name and jurisdiction require enhanced review."},
        )
        dashboard = client.get("/api/v1/dashboard")

        pipeline = client.post(
            "/api/v1/pipeline-runs",
            json={"record_count": 5, "offline": True, "sanctions_injection_rate": 0.2},
        )
        runs = client.get("/api/v1/pipeline-runs")
        run_id = pipeline.json()["run_id"]
        artifact = client.get(f"/artifacts/{run_id}/kyc-compliance-report.xlsx")

    assert workbench.status_code == 200
    assert "ClearTrace" in workbench.text
    assert stylesheet.status_code == 200
    assert initial_dashboard.json()["customer_count"] == 0
    assert assessment.status_code == 200
    assert assessment.json()["cases_created"] >= 1
    assert len(cases.json()) >= 1
    assert decision.json()["status"] == "escalated"
    assert dashboard.json()["active_case_count"] >= 1
    assert dashboard.json()["audit_event_count"] == 3
    assert runs.json()[0]["run_id"] == run_id
    assert artifact.status_code == 200
    assert artifact.headers["content-type"].startswith("application/vnd.openxmlformats")


def test_benchmark_evaluation_api(test_settings) -> None:
    with TestClient(create_app(test_settings)) as client:
        info = client.get("/api/v1/evaluations/benchmark/info")
        evaluation = client.post("/api/v1/evaluations/benchmark/runs")
        run_id = evaluation.json()["run_id"]
        runs = client.get("/api/v1/evaluations/benchmark/runs")
        artifact = client.get(f"/artifacts/evaluations/{run_id}/threshold-sweep.csv")

    assert info.status_code == 200
    assert info.json()["customer_count"] == 66
    assert info.json()["screening_positive_count"] == 24
    assert evaluation.status_code == 200
    assert evaluation.json()["screening"]["alerts"]["f1"] == 0.8571
    assert runs.json()[0]["run_id"] == run_id
    assert artifact.status_code == 200
    assert "threshold,precision,recall,f1" in artifact.text
