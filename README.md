# Multi-Agent Healthcare Workflow System

A small multi-agent AI system where three specialized agents collaborate to
research, analyze, and report on a healthcare question — with results
streamed live to a React frontend.git checkout main

Ask a question like _"What are best practices for reducing ICU readmission
rates?"_ and watch:

1. **Researcher** searches the web for current information (via SerperAPI)
2. **Analyst** synthesizes the findings into structured insights
3. **Reporter** formats everything into a polished Markdown report

...each step streamed to the UI in real time as it completes.

---

## Demo

> _Add a screen recording or screenshot here showing a query running end to
> end — the live progress updates are the most interesting part._

---

## Architecture

```
React (Vite)  ──POST /run──>  FastAPI (SSE stream)  ──>  CrewAI Crew
                                                            ├─ Researcher (SerperAPI tool)
                                                            ├─ Analyst
                                                            └─ Reporter
                                                                │
                               <── SSE events ────────────────┘
                          (status, progress, result, usage, error)
```

The backend streams 5 event types over Server-Sent Events:

| Event      | Sent when                                               |
| ---------- | ------------------------------------------------------- |
| `status`   | Once, when the crew starts                              |
| `progress` | After each agent (Researcher/Analyst/Reporter) finishes |
| `result`   | The final Markdown report                               |
| `usage`    | Token usage, estimated cost, and Serper API call count  |
| `error`    | If the crew fails, includes which agent it failed at    |

---

## Tech stack

- **[CrewAI](https://github.com/crewAIInc/crewAI)** — multi-agent orchestration
- **FastAPI** + **sse-starlette** — backend API with SSE streaming
- **React** + **Vite** — frontend
- **[SerperAPI](https://serper.dev)** — web search tool (free tier: 2,500 searches)
- **[OpenRouter](https://openrouter.ai)** — LLM access (configured to use a free model by default)
- **tenacity** — retry logic with exponential backoff

---

## Project structure

```
healthcare-crew/
├── backend/
│   ├── main.py          # FastAPI app, /run SSE endpoint
│   ├── config.py         # All settings, env-driven
│   ├── agents.py          # The 3 agent definitions
│   ├── crew.py             # Task/Crew assembly + retry logic
│   ├── tools.py             # SerperAPI search tool
│   ├── monitoring.py         # Logging, progress tracking, cost tracking
│   ├── test_crew.py            # CLI: run the crew standalone
│   └── test_api_stream.py       # CLI: test the live API stream
├── frontend/
│   └── src/
│       ├── App.jsx          # Main UI + SSE client
│       └── App.css
├── docs/
│   └── PROJECT_GUIDE.md     # In-depth walkthrough of every phase/file
├── requirements.txt
├── .env.example
└── docker-compose.yml        # Container scaffold (optional)
```

---

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- A free [OpenRouter](https://openrouter.ai/keys) API key
- A free [Serper](https://serper.dev) API key

### Backend

```bash
cd healthcare-crew
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # then fill in your API keys

cd backend
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**.

---

## Environment variables

| Variable                 | Description                                                     |
| ------------------------ | --------------------------------------------------------------- |
| `OPENROUTER_API_KEY`     | Your OpenRouter API key                                         |
| `LLM_MODEL`              | Model identifier, e.g. `openrouter/nex-agi/nex-n2-pro:free`     |
| `SERPER_API_KEY`         | Your Serper API key                                             |
| `CREWAI_TRACING_ENABLED` | Set to `false` to disable CrewAI's interactive telemetry prompt |

See `.env.example` for the full list, including retry and rate-limit tuning.

---

## Testing without the frontend

```bash
cd backend

# Run the crew directly and print the report + usage report
python test_crew.py "Your healthcare question here"

# Or test the live API's SSE stream
python test_api_stream.py "Your healthcare question here"
```

---

## Notes

- The default model is a **free** OpenRouter model — responses are not
  guaranteed to be deterministic, and search/token usage can vary
  significantly between runs.
- This project skips authentication, a database, and deployment by design —
  it's meant to run locally.
- See `docs/PROJECT_GUIDE.md` for a detailed, phase-by-phase explanation of
  how the system was built.

---

## License

MIT
