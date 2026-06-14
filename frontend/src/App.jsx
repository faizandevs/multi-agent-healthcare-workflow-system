import { useState, useRef } from "react";
import ReactMarkdown from "react-markdown";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/run";

const AGENT_LABELS = {
  "Healthcare Research Specialist": "Researcher",
  "Healthcare Data Analyst": "Analyst",
  "Medical Report Writer": "Reporter",
};

function App() {
  const [query, setQuery] = useState("");
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState([]);
  const [report, setReport] = useState(null);
  const [usage, setUsage] = useState(null);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);

  function handleEvent(eventType, data) {
    switch (eventType) {
      case "status":
        setProgress((prev) => [
          ...prev,
          { key: "status", label: data.message },
        ]);
        break;
      case "progress": {
        const label = AGENT_LABELS[data.agent] || data.agent;
        setProgress((prev) => [
          ...prev,
          {
            key: `progress-${prev.length}`,
            label: `${label} completed (${data.duration_seconds}s)`,
          },
        ]);
        break;
      }
      case "result":
        setReport(data.report);
        break;
      case "usage":
        setUsage(data.usage);
        break;
      case "error":
        setError({ failedAgent: data.failed_agent, message: data.message });
        break;
      default:
        break;
    }
  }

  async function handleRun() {
    if (!query.trim() || running) return;

    setRunning(true);
    setProgress([]);
    setReport(null);
    setUsage(null);
    setError(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`Server returned ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentEvent = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() ?? ""; // keep incomplete line for next chunk

        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEvent = line.slice("event:".length).trim();
          } else if (line.startsWith("data:")) {
            const dataStr = line.slice("data:".length).trim();
            if (!dataStr) continue;
            try {
              const data = JSON.parse(dataStr);
              handleEvent(currentEvent, data);
            } catch {
              // ignore malformed lines
            }
          }
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        setError({ message: err.message });
      }
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Healthcare Workflow Assistant</h1>
        <p>
          Ask a clinical or operational healthcare question. Three AI agents
          research, analyze, and produce a structured report.
        </p>
      </header>

      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="e.g. What are best practices for reducing ICU readmission rates?"
        rows={3}
        disabled={running}
      />

      <button onClick={handleRun} disabled={running || !query.trim()}>
        {running ? "Running…" : "Run"}
      </button>

      {progress.length > 0 && (
        <section className="card">
          <h2>Progress</h2>
          <ul className="progress-list">
            {progress.map((item) => (
              <li key={item.key}>{item.label}</li>
            ))}
          </ul>
        </section>
      )}

      {error && (
        <section className="card error">
          <h2>Something went wrong</h2>
          {error.failedAgent && (
            <p>
              Failed at agent:{" "}
              <strong>
                {AGENT_LABELS[error.failedAgent] || error.failedAgent}
              </strong>
            </p>
          )}
          <p className="error-detail">{error.message}</p>
        </section>
      )}

      {report && (
        <section className="card report">
          <h2>Report</h2>
          <ReactMarkdown>{report}</ReactMarkdown>
        </section>
      )}

      {usage && (
        <section className="card usage">
          <h2>Usage &amp; cost</h2>
          <table>
            <tbody>
              <tr>
                <td>Model</td>
                <td>{usage.llm.model}</td>
              </tr>
              <tr>
                <td>Prompt tokens</td>
                <td>{usage.llm.tokens.prompt_tokens.toLocaleString()}</td>
              </tr>
              <tr>
                <td>Completion tokens</td>
                <td>{usage.llm.tokens.completion_tokens.toLocaleString()}</td>
              </tr>
              <tr>
                <td>Total tokens</td>
                <td>{usage.llm.tokens.total_tokens.toLocaleString()}</td>
              </tr>
              <tr>
                <td>Estimated cost</td>
                <td>${usage.llm.cost.total_cost_usd?.toFixed(6) ?? "n/a"}</td>
              </tr>
              <tr>
                <td>Serper calls (all-time)</td>
                <td>
                  {usage.serper.total_calls_all_time} /{" "}
                  {usage.serper.free_tier_limit} ({usage.serper.remaining}{" "}
                  remaining)
                </td>
              </tr>
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}

export default App;
