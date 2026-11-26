from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_db
from app.main import app


def test_health_reports_db_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_health_reports_db_down_visibly(client: TestClient) -> None:
    # Port 1 refuses connections, so SELECT 1 fails.
    broken_engine = create_engine("postgresql+psycopg://terra:x@localhost:1/terra_test", connect_args={"connect_timeout": 1})
    broken_factory = sessionmaker(bind=broken_engine)

    def _broken_db() -> Iterator[Session]:
        session = broken_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _broken_db
    try:
        response = client.get("/health")
    finally:
        broken_engine.dispose()

    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": "error"}
