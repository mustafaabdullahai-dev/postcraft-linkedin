"""Application context: wires providers + services + workflow together."""
from __future__ import annotations

from pathlib import Path

from app.agents.graph import LinkedInWorkflow
from app.agents.nodes import NodeContext
from app.core.config import Settings
from app.models.post import PostStore
from app.models.user import UserStore
from app.services.google_sheets import GoogleSheetsService
from app.services.image_generation import get_image_provider
from app.services.linkedin import LinkedInPublisher
from app.services.llm import get_text_provider


class ApplicationContext:
    """Single composition root for the whole app."""

    def __init__(self, settings: Settings):
        self.settings = settings

        data_dir = Path(settings.data_dir).expanduser()
        if not data_dir.is_absolute():
            data_dir = Path.cwd() / data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = data_dir

        self.text_provider = get_text_provider(settings)
        self.image_provider = get_image_provider(settings)
        self.linkedin_publisher = LinkedInPublisher(settings)
        self.sheets_service = GoogleSheetsService(settings, data_dir / "audit.jsonl")
        self.store = PostStore(data_dir)
        self.user_store = UserStore(data_dir)

        self.node_context = NodeContext(
            text_provider=self.text_provider,
            image_provider=self.image_provider,
            linkedin_publisher=self.linkedin_publisher,
            sheets_service=self.sheets_service,
            store=self.store,
            user_store=self.user_store,
            settings=settings,
        )
        self.workflow = LinkedInWorkflow(self.node_context)


__all__ = ["ApplicationContext"]