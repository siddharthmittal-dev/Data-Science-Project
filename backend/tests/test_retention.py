from datetime import date, timedelta
import pytest

from app.services.retention import patient_features, probability
from app.train_retention import train, snapshots


@pytest.fixture(scope="module")
def model():
    return train(date(2026, 11, 21))


def test_mature_labels_and_feature_cutoff(model):
    cutoff = date(2026, 10, 1)
    events = [{"day": cutoff - timedelta(days=20), "status": "completed"},
              {"day": cutoff + timedelta(days=3), "status": "completed"}]
    assert patient_features(events, cutoff)[0] == 20
    assert patient_features([], cutoff) is None
    with pytest.raises(ValueError):
        snapshots([events], [cutoff], cutoff + timedelta(days=30))
    assert model["training_label_end"] <= model["validation_origin"]
    assert date.fromisoformat(model["validation_origin"]) + timedelta(days=90) <= date.fromisoformat(model["holdout_origin"])
    assert 0 <= probability([20, 2, 3, 45, 0, 0], model) <= 1
    assert model["metrics"]["holdout"]["logistic"]["samples"] > 400


def test_retention_staff_only_and_task_workflow(login):
    assert login("patient").get("/api/retention").status_code == 403
    staff = login("admin")
    overview = staff.get("/api/retention")
    assert overview.status_code == 200
    assert len(overview.json()["patients"]) == 3
    response = staff.post("/api/retention/tasks", json={"patient_id": 1, "note": "Review existing booking before any follow-up"})
    assert response.status_code == 201
    task_id = response.json()["id"]
    assert staff.post("/api/retention/tasks", json={"patient_id": 1, "note": "duplicate"}).status_code == 409
    assert staff.post(f"/api/retention/tasks/{task_id}/complete", json={"outcome": " "}).status_code == 422
    assert staff.post(f"/api/retention/tasks/{task_id}/complete", json={"outcome": "Existing booking confirmed; no outreach"}).status_code == 200
    assert staff.post(f"/api/retention/tasks/{task_id}/complete", json={"outcome": "repeat"}).status_code == 409
    task = staff.get("/api/retention").json()["tasks"][0]
    assert task["status"] == "completed"
    assert "Existing booking" in task["outcome"]


def test_return_score_does_not_use_future_completions(model):
    cutoff = date(2026, 11, 1)
    events = [{"day": cutoff - timedelta(days=10), "status": "completed"}]
    before = probability(patient_features(events, cutoff), model)
    events.append({"day": cutoff + timedelta(days=10), "status": "completed"})
    assert probability(patient_features(events, cutoff), model) == before
