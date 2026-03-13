"""Shared test fixtures."""

import sys

sys.path.insert(0, "/home/canary/tenerife-tourism/backend")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, init_db
from app.main import app

# Ensure tables exist
init_db()


@pytest.fixture
def db():
    """Provide a database session for tests."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    """Provide a FastAPI test client."""
    return TestClient(app)
