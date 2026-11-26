import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

TEST_DATABASE_URL = get_settings().test_database_url
# Tests truncate every table. Refuse to run against anything but a *_test database.
assert make_url(TEST_DATABASE_URL).database.endswith("_test"), "TEST_DATABASE_URL must point to a *_test database"


@pytest.fixture(scope="session", autouse=True)
def migrated_db() -> Iterator[None]:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(scope="session")
def test_session_factory(migrated_db: None) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture(autouse=True)
def seeded(test_session_factory: sessionmaker[Session]) -> None:
    # seed() truncates every table (RESTART IDENTITY CASCADE) before inserting.
    with test_session_factory() as session:
        seed(session)


@pytest.fixture(autouse=True)
def _override_get_db(test_session_factory: sessionmaker[Session]) -> Iterator[None]:
    def _get_test_db() -> Iterator[Session]:
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def db(test_session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = test_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def login(test_session_factory):
    def _login(role: str) -> TestClient:
        from app.models import User
        from app.services.passwords import hash_password
        from sqlalchemy import select
        # Give seeded fixtures credentials only inside the guarded test database.
        with test_session_factory() as db:
            user = db.scalar(select(User).where(User.role == role).order_by(User.id))
            user.password_hash = hash_password("Fixture-password-42")
            email = user.email
            db.commit()
        test_client = TestClient(app)
        response = test_client.post("/api/auth/login", json={"email": email, "password": "Fixture-password-42"})
        assert response.status_code == 200, response.text
        return test_client

    return _login
