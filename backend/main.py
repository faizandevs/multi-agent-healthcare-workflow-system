"""
FastAPI app exposing /run, which kicks off the healthcare crew and streams
progress + the final report back to the client via Server-Sent Events (SSE).

Because crew.kickoff() is blocking/synchronous, each request runs the crew
in a background thread (via run_in_executor) while the async generator below
reads progress messages from a thread-safe queue and forwards them as SSE
events.

SSE event types (see crew.run_crew_streaming for full shapes):
  status   - one-time "starting" message
  progress - sent after each agent (Researcher/Analyst/Reporter) completes
  result   - the final Markdown report
  usage    - token/cost/Serper usage report
  error    - sent instead of result/usage if the crew failed
"""

import asyncio
import json
import queue

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from dotenv import load_dotenv

from crew import run_crew_streaming

load_dotenv()

app = FastAPI(title="Healthcare Crew API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    query: str


@app.get("/health")
async def health():
    return {"status": "ok"}


async def event_stream(query: str):
    progress_queue: queue.Queue = queue.Queue()
    loop = asyncio.get_event_loop()

    # Run the blocking crew in a background thread so this generator stays
    # free to read from the queue and yield events as they arrive.
    crew_future = loop.run_in_executor(None, run_crew_streaming, query, progress_queue)

    try:
        while True:
            # queue.get() blocks, so offload it to a thread too — this lets
            # the event loop keep serving other requests while we wait.
            item = await loop.run_in_executor(None, progress_queue.get)

            if item["type"] == "done":
                break

            yield {"event": item["type"], "data": json.dumps(item)}
    finally:
        # Ensure the background thread is awaited (propagates any truly
        # unexpected exception not already caught inside run_crew_streaming).
        await crew_future


@app.post("/run")
async def run_crew_endpoint(request: RunRequest):
    return EventSourceResponse(event_stream(request.query))