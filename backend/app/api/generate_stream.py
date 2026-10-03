"""Server-sent progress events for post generation.

The generation pipeline is a LangGraph graph with a fan-out, so node
completion order is not strictly linear. The UI needs a *monotonic* list of
stages it can tick off truthfully, which is what STAGES encodes: a stage counts
as done only once every node it owns has completed.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Dict, List

# Ordered user-facing stages. `nodes` must cover every node that
# `LinkedInWorkflow.run_generation` executes, otherwise a node would silently
# leave its stage stuck on "active".
STAGES: List[Dict[str, Any]] = [
    {"key": "brief", "label": "Shaping your idea into a clear brief", "nodes": ["analyze_topic"]},
    {"key": "copy", "label": "Writing the post copy", "nodes": ["plan_content", "generate_linkedin_post"]},
    {
        "key": "extras",
        "label": "Adding hashtags and the image brief",
        "nodes": ["generate_hashtags", "generate_image_prompt"],
    },
    {"key": "visual", "label": "Generating the visual", "nodes": ["generate_image"]},
    {"key": "quality", "label": "Checking quality & the hook", "nodes": ["validate_content"]},
    # LangGraph never reports `human_review` as a completed node — the run
    # halts inside it, so the interrupt pseudo-node is what actually fires.
    {"key": "review", "label": "Preparing your review", "nodes": ["__interrupt__"]},
]

_STAGE_BY_NODE: Dict[str, str] = {
    node: stage["key"] for stage in STAGES for node in stage["nodes"]
}


def stage_key_for(node: str) -> str | None:
    """Map a graph node name onto its UI stage key."""
    return _STAGE_BY_NODE.get(node)


def stage_snapshot(completed_nodes: set[str]) -> Dict[str, Any]:
    """Describe the checklist truthfully given the nodes finished so far.

    Returns the ordered stage list where each entry carries its true state, plus
    `active_index` — the first stage still in flight, or None when all are done.
    Stages are never reported out of order even though the graph fans out.
    """
    stages = []
    active_index: int | None = None
    for index, stage in enumerate(STAGES):
        done = all(node in completed_nodes for node in stage["nodes"])
        # Freeze the pointer at the first incomplete stage: a later stage that
        # finished early (the image branch) must not skip ahead of an earlier one.
        if not done and active_index is None:
            active_index = index
        stages.append(
            {
                "key": stage["key"],
                "label": stage["label"],
                "done": done,
                "active": index == active_index,
            }
        )
    if active_index is None:
        active_index = len(STAGES)
    return {"stages": stages, "active_index": active_index}


def sse(event: str, data: Dict[str, Any]) -> str:
    """Encode one SSE frame."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def progress_stream(
    queue: "asyncio.Queue[Dict[str, Any] | None]",
) -> AsyncIterator[str]:
    """Drain `queue` into SSE frames until the sentinel `None` arrives."""
    while True:
        item = await queue.get()
        if item is None:
            return
        yield sse(item.pop("event"), item)


def publish(queue: "asyncio.Queue[Dict[str, Any] | None]", event: str, **data: Any) -> None:
    """Queue one SSE frame; never block the workflow if the client vanished."""
    try:
        queue.put_nowait({"event": event, **data})
    except Exception:  # noqa: BLE001
        pass


def close_stream(queue: "asyncio.Queue[Dict[str, Any] | None]") -> None:
    """Push the sentinel that ends `progress_stream` and closes the response.

    Without this the generator keeps awaiting `queue.get()` forever, so the
    client hangs until its own read timeout instead of seeing a clean end.
    """
    try:
        queue.put_nowait(None)
    except Exception:  # noqa: BLE001
        pass