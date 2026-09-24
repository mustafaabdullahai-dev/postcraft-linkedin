"""LangGraph workflow: generate → review → (approve) → publish → audit."""
from __future__ import annotations

import asyncio
import functools
from typing import Any, Dict, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from app.agents.nodes import (
    NodeContext,
    analyze_topic,
    generate_hashtags,
    generate_image,
    generate_image_prompt,
    generate_linkedin_post,
    human_review,
    plan_content,
    publish_to_linkedin,
    save_to_google_sheets,
    validate_content,
)
from app.agents.state import LinkedInPostState
from app.core.logging import get_logger
from app.models.user import LinkedInUser

logger = get_logger(__name__)


def _bind(node, ctx: NodeContext):
    return functools.partial(node, ctx=ctx)


def build_graph(ctx: NodeContext):
    """Compile the workflow graph with an in-memory checkpointer.

    Production note: swap MemorySaver for RedisPostgresSaver/PostgresSaver
    when running multiple processes.
    """
    g = StateGraph(LinkedInPostState)

    g.add_node("analyze_topic", _bind(analyze_topic, ctx))
    g.add_node("plan_content", _bind(plan_content, ctx))
    g.add_node("generate_linkedin_post", _bind(generate_linkedin_post, ctx))
    g.add_node("generate_hashtags", _bind(generate_hashtags, ctx))
    g.add_node("generate_image_prompt", _bind(generate_image_prompt, ctx))
    g.add_node("generate_image", _bind(generate_image, ctx))
    g.add_node("validate_content", _bind(validate_content, ctx))
    g.add_node("human_review", _bind(human_review, ctx))
    g.add_node("publish_to_linkedin", _bind(publish_to_linkedin, ctx))
    g.add_node("save_to_google_sheets", _bind(save_to_google_sheets, ctx))

    g.add_edge(START, "analyze_topic")
    g.add_edge("analyze_topic", "plan_content")
    g.add_edge("plan_content", "generate_linkedin_post")

    # Fan-out: hashtags and image prompt only need the post, so run together.
    g.add_edge("generate_linkedin_post", "generate_hashtags")
    g.add_edge("generate_linkedin_post", "generate_image_prompt")
    # Two independent branches after the fan-out:
    #   a) hashtags -> validation
    #   b) image prompt -> image render (slow async provider job)
    g.add_edge("generate_hashtags", "validate_content")
    g.add_edge("generate_image_prompt", "generate_image")
    # Fan-in (join): the review interrupt waits for BOTH branches, so the
    # (slow) image render overlaps the validation work instead of stacking.
    g.add_edge("generate_image", "human_review")
    g.add_edge("validate_content", "human_review")

    g.add_conditional_edges(
        "human_review",
        lambda state: "publish" if state.get("user_approved") else "end",
        {"publish": "publish_to_linkedin", "end": END},
    )
    g.add_edge("publish_to_linkedin", "save_to_google_sheets")
    g.add_edge("save_to_google_sheets", END)

    return g.compile(checkpointer=MemorySaver())


class LinkedInWorkflow:
    """High-level wrapper used by API routes."""

    def __init__(self, ctx: NodeContext):
        self.ctx = ctx
        self.graph = build_graph(ctx)

    def _config(self, record_id: str) -> Dict[str, Any]:
        return {"configurable": {"thread_id": record_id}}

    async def run_generation(
        self,
        user_query: str,
        record_id: str,
        seed: Optional[Dict[str, Any]] = None,
        user: Optional[LinkedInUser] = None,
    ) -> Dict[str, Any]:
        """Run the generation pipeline. Halts at the human-review interrupt."""
        initial: Dict[str, Any] = {
            "user_query": user_query,
            "record_id": record_id,
            "owner_id": user.user_id if user else "",
            "linkedin_user": user.model_dump(mode="json") if user else {},
            "review_status": "PENDING",
            "user_approved": False,
        }
        if seed:
            initial.update(seed)

        updates: list[Dict[str, Any]] = []
        started = asyncio.get_event_loop().time()
        async for event in self.graph.astream(
            initial, self._config(record_id), stream_mode="updates"
        ):
            updates.append(event)
            node = list(event.keys())[0] if event else None
            logger.info(
                "workflow update",
                node=node,
                elapsed_ms=round((asyncio.get_event_loop().time() - started) * 1000),
            )

        state = await self.graph.aget_state(self._config(record_id))
        return self._merge(state)

    async def approve_and_publish(
        self,
        record_id: str,
        approved: bool = True,
        resume_update: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Resume the graph at human_review with the user's decision.

        `resume_update` merges edited state (e.g. edited_post / hashtags)
        into the thread as part of the same resume command — this avoids
        LangGraph's ambiguous `update_state` on joined (fan-in) graphs.
        """
        update = Command(resume=approved, update=resume_update or {})

        started = asyncio.get_event_loop().time()
        async for event in self.graph.astream(
            update, self._config(record_id), stream_mode="updates"
        ):
            logger.info(
                "workflow resume update",
                node=list(event.keys())[0] if event else None,
                elapsed_ms=round((asyncio.get_event_loop().time() - started) * 1000),
            )

        state = await self.graph.aget_state(self._config(record_id))
        return self._merge(state)

    async def set_state(self, record_id: str, fields: Dict[str, Any]) -> None:
        """Write fields (e.g. edited_post) into the thread state before resume.

        Prefer `approve_and_publish(..., resume_update=fields)` instead —
        update_state is ambiguous on joined graphs. This stays for tests /
        roll-out cases where the graph is NOT paused at an interrupt.
        """
        await self.graph.aupdate_state(self._config(record_id), fields)

    async def retry_publish(
        self, state: Dict[str, Any], user: Optional[LinkedInUser] = None
    ) -> Dict[str, Any]:
        """Re-run publish + audit nodes directly (used for publish retries).

        Only call AFTER the API has verified `approval_status == APPROVED`.
        The approval gate is enforced server-side here.
        """
        from app.agents.nodes.content_nodes import publish_to_linkedin, save_to_google_sheets

        working = dict(state)
        working["user_approved"] = True
        if user is not None:
            working["owner_id"] = user.user_id
            working["linkedin_user"] = user.model_dump(mode="json")
        publish_result = await publish_to_linkedin(working, ctx=self.ctx)
        working.update(publish_result)
        sheets_result = await save_to_google_sheets(working, ctx=self.ctx)
        working.update(sheets_result)
        return working

    def _merge(self, snapshot) -> Dict[str, Any]:
        values = dict(snapshot.values or {})
        # Normalise for convenience of the API layer.
        normalized = {k: v for k, v in values.items() if v is not None}
        return normalized


__all__ = ["build_graph", "LinkedInWorkflow", "NodeContext"]