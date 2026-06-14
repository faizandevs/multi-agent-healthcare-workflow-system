"""
Crew assembly: wires the 3 agents into a sequential pipeline, with:
  - per-agent progress logging (task_callback)
  - retry with exponential backoff on the whole crew run
  - error messages that identify which agent's task likely failed
  - a streaming variant (run_crew_streaming) for the FastAPI SSE endpoint

Flow:
  research_task  -> Researcher searches the web for the query
  analysis_task  -> Analyst synthesizes the research output
  report_task    -> Reporter formats the final structured report
"""

from crewai import Crew, Task, Process
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from agents import researcher, analyst, reporter
from config import (
    CREW_MAX_RETRIES,
    CREW_RETRY_MIN_WAIT_SECONDS,
    CREW_RETRY_MAX_WAIT_SECONDS,
)
from monitoring import TaskProgressTracker, logger, print_usage_report, build_usage_report


# Ordered list — used to figure out which agent was "next" if the crew
# fails before any task_callback fires (e.g. first task crashes).
AGENT_ORDER = ["Healthcare Research Specialist", "Healthcare Data Analyst", "Medical Report Writer"]


class CrewExecutionError(Exception):
    """
    Raised when the crew fails, with attribution to the agent most likely
    responsible — either the last one that completed, or the first one
    in the pipeline if nothing completed yet.
    """

    def __init__(self, message: str, failed_agent: str, original_exception: Exception):
        super().__init__(message)
        self.failed_agent = failed_agent
        self.original_exception = original_exception


def build_crew(query: str, tracker: TaskProgressTracker) -> Crew:
    research_task = Task(
        description=(
            f"Research the following healthcare query using web search:\n\n"
            f'"{query}"\n\n'
            "Find current, credible information. Note the source for each "
            "key finding."
        ),
        expected_output=(
            "A list of 3-5 key findings, each with a one-line source "
            "attribution."
        ),
        agent=researcher,
    )

    analysis_task = Task(
        description=(
            "Review the research findings and synthesize them into key "
            "insights. Identify: (1) main themes, (2) areas of consensus, "
            "(3) any conflicting information or caveats."
        ),
        expected_output=(
            "A structured synthesis with clear themes, consensus points, "
            "and caveats."
        ),
        agent=analyst,
        context=[research_task],
    )

    report_task = Task(
        description=(
            "Using the analyst's synthesis, write a final structured report "
            "for a healthcare professional audience. Include: a title, an "
            "executive summary, key findings as bullet points, and a brief "
            "'Important note' disclaimer that this is informational and not "
            "medical advice."
        ),
        expected_output=(
            "A Markdown-formatted report with headings, bullet points, and "
            "a disclaimer section."
        ),
        agent=reporter,
        context=[analysis_task],
    )

    return Crew(
        agents=[researcher, analyst, reporter],
        tasks=[research_task, analysis_task, report_task],
        process=Process.sequential,
        verbose=True,
        task_callback=tracker,
    )


@retry(
    stop=stop_after_attempt(CREW_MAX_RETRIES + 1),
    wait=wait_exponential(
        multiplier=1,
        min=CREW_RETRY_MIN_WAIT_SECONDS,
        max=CREW_RETRY_MAX_WAIT_SECONDS,
    ),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _kickoff_with_retry(crew: Crew):
    return crew.kickoff()


def _attribute_failure(tracker: TaskProgressTracker, exc: Exception) -> CrewExecutionError:
    """
    Shared failure-attribution logic for both the sync (run_crew) and
    streaming (run_crew_streaming) entry points.
    """
    last_completed = tracker.last_completed_agent
    if last_completed is None:
        failed_agent = AGENT_ORDER[0]
    else:
        idx = AGENT_ORDER.index(last_completed) if last_completed in AGENT_ORDER else -1
        failed_agent = AGENT_ORDER[idx + 1] if 0 <= idx < len(AGENT_ORDER) - 1 else last_completed

    logger.error(f"Crew failed. Attributed to agent: {failed_agent}. Error: {exc}")
    return CrewExecutionError(
        f"Crew run failed at agent '{failed_agent}' after "
        f"{CREW_MAX_RETRIES + 1} attempt(s): {exc}",
        failed_agent=failed_agent,
        original_exception=exc,
    )


def run_crew(query: str) -> str:
    """
    Runs the full crew synchronously, retrying the whole pipeline on
    transient failures (rate limits, network blips). Returns the final
    report text.

    Used by test_crew.py (CLI). Raises CrewExecutionError with
    .failed_agent set if all retries fail.
    """
    tracker = TaskProgressTracker()
    crew = build_crew(query, tracker)

    try:
        result = _kickoff_with_retry(crew)
    except Exception as exc:
        raise _attribute_failure(tracker, exc) from exc

    print_usage_report(crew)
    return str(result)


def run_crew_streaming(query: str, progress_queue) -> None:
    """
    Runs the full crew, pushing progress events onto `progress_queue` (a
    thread-safe queue.Queue) as they happen. Designed to be run in a
    background thread by the FastAPI SSE endpoint.

    Event shapes pushed onto the queue:
      {"type": "status",   "message": "..."}                         - sent once at start
      {"type": "progress", "agent": "...", "duration_seconds": ...,
                            "message": "..."}                          - sent after each task
      {"type": "result",   "report": "..."}                           - sent once on success
      {"type": "usage",    "usage": {...}}                             - sent once on success
      {"type": "error",    "failed_agent": "...", "message": "..."}    - sent once on failure
      {"type": "done"}                                                 - always sent last

    Never raises — all exceptions are caught and converted to an "error"
    event so the SSE stream always terminates cleanly.
    """
    progress_queue.put({
        "type": "status",
        "message": f"Starting crew for query: {query}",
    })

    tracker = TaskProgressTracker(progress_queue=progress_queue)
    crew = build_crew(query, tracker)

    try:
        result = _kickoff_with_retry(crew)
    except Exception as exc:
        crew_error = _attribute_failure(tracker, exc)
        progress_queue.put({
            "type": "error",
            "failed_agent": crew_error.failed_agent,
            "message": str(crew_error.original_exception),
        })
        progress_queue.put({"type": "done"})
        return

    usage = build_usage_report(crew)
    progress_queue.put({"type": "result", "report": str(result)})
    progress_queue.put({"type": "usage", "usage": usage})
    progress_queue.put({"type": "done"})