"""
Centralized configuration — everything that might change between local dev,
Docker, and a future deployment lives here, driven by environment variables.

This is the single place to look when containerizing: every value below
should come from .env / docker-compose env vars, never hardcoded elsewhere.
"""

import os

# --- LLM configuration ---
# LiteLLM (used internally by CrewAI) routes based on the model string prefix.
# Examples:
#   OpenAI direct:     "gpt-4o-mini"
#   OpenRouter:        "openrouter/nex-agi/nex-n2-pro:free"
#   OpenRouter (other):"openrouter/poolside/laguna-m.1:free"
#
# When using "openrouter/..." models, LiteLLM reads OPENROUTER_API_KEY from
# the environment automatically — no code change needed to switch models,
# just update LLM_MODEL below (or in .env).
LLM_MODEL = os.getenv("LLM_MODEL", "openrouter/nex-agi/nex-n2-pro:free")

# Pricing in USD per 1,000 tokens. Used for cost estimation in the usage
# report. Free models should map to 0/0 — add entries as you try new models.
PRICING_PER_1K = {
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.00060},
    "gpt-4o": {"prompt": 0.0025, "completion": 0.0100},
    "gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
    "openrouter/nex-agi/nex-n2-pro:free": {"prompt": 0.0, "completion": 0.0},
    "openrouter/poolside/laguna-m.1:free": {"prompt": 0.0, "completion": 0.0},
}

# --- Retry behavior ---
CREW_MAX_RETRIES = int(os.getenv("CREW_MAX_RETRIES", "2"))
CREW_RETRY_MIN_WAIT_SECONDS = int(os.getenv("CREW_RETRY_MIN_WAIT_SECONDS", "2"))
CREW_RETRY_MAX_WAIT_SECONDS = int(os.getenv("CREW_RETRY_MAX_WAIT_SECONDS", "10"))

# --- Agent loop / rate-limit tuning ---
# Caps how many reasoning steps an agent can take before being forced to
# produce a Final Answer. The Researcher gets more room since it needs to
# call the search tool and reason over results; Analyst/Reporter have no
# tools and should converge faster.
RESEARCHER_MAX_ITER = int(os.getenv("RESEARCHER_MAX_ITER", "8"))
ANALYST_MAX_ITER = int(os.getenv("ANALYST_MAX_ITER", "5"))
REPORTER_MAX_ITER = int(os.getenv("REPORTER_MAX_ITER", "5"))

# Caps requests-per-minute per agent. OpenRouter's free tier allows 20
# req/min account-wide; staying under that proactively avoids 429s (which
# themselves consume retry attempts and tokens).
AGENT_MAX_RPM = int(os.getenv("AGENT_MAX_RPM", "15"))

# --- OpenRouter free-tier awareness (only relevant if LLM_MODEL starts with
# "openrouter/" and the key has no credit added) ---
# Free tier: 20 requests/minute, 50 requests/day. With $10+ lifetime credit
# added to the OpenRouter account, the daily limit rises to 1000.
OPENROUTER_FREE_DAILY_LIMIT = int(os.getenv("OPENROUTER_FREE_DAILY_LIMIT", "50"))
OPENROUTER_USAGE_FILE = os.getenv("OPENROUTER_USAGE_FILE", "openrouter_usage.json")

# --- SerperAPI free tier awareness ---
# Free tier is 2,500 searches total (not monthly) as of writing — verify on
# serper.dev/dashboard. This is just a local soft-warning threshold.
SERPER_FREE_TIER_LIMIT = int(os.getenv("SERPER_FREE_TIER_LIMIT", "2500"))
SERPER_USAGE_FILE = os.getenv("SERPER_USAGE_FILE", "serper_usage.json")