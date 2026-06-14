"""
Custom tools available to agents.

CountingSerperDevTool wraps Serper.dev's Google Search API and increments a
persisted call counter on every invocation, so we always know how close we
are to the free-tier limit (see monitoring.increment_serper_calls).
"""

from crewai_tools import SerperDevTool
from monitoring import increment_serper_calls, logger


class CountingSerperDevTool(SerperDevTool):
    """SerperDevTool subclass that tracks usage against the free-tier quota."""

    def _run(self, *args, **kwargs):
        total = increment_serper_calls(1)
        logger.info(f"[SerperAPI] call #{total} (this run)")
        return super()._run(*args, **kwargs)


search_tool = CountingSerperDevTool()