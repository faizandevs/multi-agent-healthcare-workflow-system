"""
Observability layer: per-agent step logging, token/cost tracking, and
SerperAPI call counting.

Designed to be cheap and dependency-light — plain JSON file for persistence,
plain logging module for output. Easy to swap for Prometheus/structured
logging later without touching the agent/crew code.
"""

import json
import logging
import os
import time
from pathlib import Path

from config import (
    LLM_MODEL,
    PRICING_PER_1K,
    SERPER_FREE_TIER_LIMIT,
    SERPER_USAGE_FILE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("healthcare_crew")


# ---------------------------------------------------------------------------
# Per-agent step / task logging
# ---------------------------------------------------------------------------

class TaskProgressTracker:
    """
    Passed to Crew(task_callback=...). CrewAI calls this after each Task
    completes with a TaskOutput object (has .agent, .raw, .description).

    Tracks which agent ran last and how long each task took — this is what
    lets us say "the Researcher agent failed" instead of a generic crash.

    If a `progress_queue` (a thread-safe queue.Queue) is provided, also
    pushes a "progress" message for each completed task — used by the
    FastAPI SSE endpoint to stream live updates to the frontend.
    """

    def __init__(self, progress_queue=None):
        self.completed_tasks = []
        self._task_start_time = time.time()
        self.progress_queue = progress_queue

    def on_task_start(self, agent_role: str):
        self._task_start_time = time.time()
        logger.info(f"[{agent_role}] started")

    def __call__(self, task_output):
        duration = time.time() - self._task_start_time
        agent_role = getattr(task_output, "agent", "unknown")
        raw_len = len(getattr(task_output, "raw", "") or "")

        logger.info(
            f"[{agent_role}] completed in {duration:.1f}s "
            f"({raw_len} chars output)"
        )
        self.completed_tasks.append(
            {"agent": agent_role, "duration_seconds": round(duration, 2)}
        )

        if self.progress_queue is not None:
            self.progress_queue.put({
                "type": "progress",
                "agent": agent_role,
                "duration_seconds": round(duration, 2),
                "message": f"{agent_role} completed in {duration:.1f}s",
            })

        # Reset timer for the next task
        self._task_start_time = time.time()

    @property
    def last_completed_agent(self) -> str | None:
        if not self.completed_tasks:
            return None
        return self.completed_tasks[-1]["agent"]


# ---------------------------------------------------------------------------
# Token usage + cost
# ---------------------------------------------------------------------------

def extract_usage_metrics(crew) -> dict:
    """
    CrewAI exposes crew.usage_metrics after kickoff() — a pydantic object
    with prompt_tokens, completion_tokens, total_tokens, successful_requests.
    Defensive .get/getattr because field availability varies by version.
    """
    metrics = getattr(crew, "usage_metrics", None)
    if metrics is None:
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "successful_requests": 0,
        }

    def _get(field):
        if isinstance(metrics, dict):
            return metrics.get(field, 0)
        return getattr(metrics, field, 0)

    return {
        "prompt_tokens": _get("prompt_tokens"),
        "completion_tokens": _get("completion_tokens"),
        "total_tokens": _get("total_tokens"),
        "successful_requests": _get("successful_requests"),
    }


def calculate_cost(usage: dict, model: str = LLM_MODEL) -> dict:
    """Returns a cost breakdown in USD based on the pricing table in config."""
    pricing = PRICING_PER_1K.get(model)
    if pricing is None:
        return {
            "model": model,
            "note": "No pricing data for this model — add it to config.PRICING_PER_1K",
            "prompt_cost_usd": None,
            "completion_cost_usd": None,
            "total_cost_usd": None,
        }

    prompt_cost = (usage["prompt_tokens"] / 1000) * pricing["prompt"]
    completion_cost = (usage["completion_tokens"] / 1000) * pricing["completion"]

    return {
        "model": model,
        "prompt_cost_usd": round(prompt_cost, 6),
        "completion_cost_usd": round(completion_cost, 6),
        "total_cost_usd": round(prompt_cost + completion_cost, 6),
    }


# ---------------------------------------------------------------------------
# SerperAPI call counter (persisted to a small JSON file)
# ---------------------------------------------------------------------------

def _usage_file_path() -> Path:
    return Path(__file__).parent / SERPER_USAGE_FILE


def increment_serper_calls(n: int = 1) -> int:
    """Increments the persisted Serper call count and returns the new total."""
    path = _usage_file_path()
    data = {"total_calls": 0}

    if path.exists():
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    data["total_calls"] = data.get("total_calls", 0) + n
    path.write_text(json.dumps(data, indent=2))

    total = data["total_calls"]
    if total >= SERPER_FREE_TIER_LIMIT:
        logger.warning(
            f"Serper usage ({total}) has reached/exceeded the configured "
            f"free-tier limit ({SERPER_FREE_TIER_LIMIT}). Check your dashboard."
        )
    elif total >= SERPER_FREE_TIER_LIMIT * 0.9:
        logger.warning(
            f"Serper usage ({total}/{SERPER_FREE_TIER_LIMIT}) is at 90%+ of "
            f"the configured free-tier limit."
        )

    return total


def get_serper_call_count() -> int:
    path = _usage_file_path()
    if not path.exists():
        return 0
    try:
        return json.loads(path.read_text()).get("total_calls", 0)
    except (json.JSONDecodeError, OSError):
        return 0


# ---------------------------------------------------------------------------
# Combined report
# ---------------------------------------------------------------------------

def build_usage_report(crew) -> dict:
    usage = extract_usage_metrics(crew)
    cost = calculate_cost(usage)
    serper_calls_total = get_serper_call_count()

    return {
        "llm": {
            "model": LLM_MODEL,
            "tokens": usage,
            "cost": cost,
        },
        "serper": {
            "total_calls_all_time": serper_calls_total,
            "free_tier_limit": SERPER_FREE_TIER_LIMIT,
            "remaining": max(SERPER_FREE_TIER_LIMIT - serper_calls_total, 0),
        },
    }


def print_usage_report(crew):
    report = build_usage_report(crew)
    print("\n=== USAGE & COST REPORT ===")
    print(json.dumps(report, indent=2))