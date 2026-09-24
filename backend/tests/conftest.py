"""Shared test fixtures: settings + full context in mock mode."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.context import ApplicationContext


@pytest.fixture()
def tmp_data_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="li_agent_test_"))


@pytest.fixture()
def settings(tmp_data_dir: Path) -> Settings:
    return Settings(
        environment="test",
        text_provider="mock",
        image_provider="mock",
        linkedin_dry_run=True,
        google_sheets_dry_run=True,
        data_dir=str(tmp_data_dir),
    )


@pytest.fixture()
def app_ctx(settings: Settings) -> ApplicationContext:
    return ApplicationContext(settings)


@pytest.fixture()
def linkedin_publisher(settings: Settings):
    from app.services.linkedin import LinkedInPublisher

    return LinkedInPublisher(settings)