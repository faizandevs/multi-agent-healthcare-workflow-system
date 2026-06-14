"""
Agent definitions for the Healthcare Workflow Crew.

Three agents, each with a single responsibility:
  1. Researcher — gathers current information via web search
  2. Analyst     — synthesizes raw research into structured insights
  3. Reporter    — formats insights into a polished, structured report

All agents share one LLM config (from config.LLM_MODEL), so switching
providers (OpenAI <-> OpenRouter <-> any other LiteLLM-supported provider)
is a single env var change — no code edits needed.
"""

from crewai import Agent, LLM
from tools import search_tool
from config import (
    LLM_MODEL,
    RESEARCHER_MAX_ITER,
    ANALYST_MAX_ITER,
    REPORTER_MAX_ITER,
    AGENT_MAX_RPM,
)

llm = LLM(model=LLM_MODEL)


researcher = Agent(
    role="Healthcare Research Specialist",
    goal=(
        "Find current, credible information relevant to the given healthcare "
        "query — clinical guidelines, operational best practices, or recent "
        "findings — using web search."
    ),
    backstory=(
        "You are a meticulous medical research assistant who has spent years "
        "helping clinicians and hospital administrators stay current with "
        "evidence-based practices. You prioritize reputable sources (medical "
        "journals, health authorities, hospital systems) and always note "
        "where information comes from."
    ),
    tools=[search_tool],
    llm=llm,
    max_iter=RESEARCHER_MAX_ITER,
    max_rpm=AGENT_MAX_RPM,
    verbose=True,
    allow_delegation=False,
)


analyst = Agent(
    role="Healthcare Data Analyst",
    goal=(
        "Synthesize the researcher's findings into clear, actionable insights, "
        "identifying key themes, points of consensus, and any conflicting "
        "information."
    ),
    backstory=(
        "You are an experienced healthcare analyst who translates raw "
        "research into insights that clinicians and administrators can act "
        "on. You are precise, avoid jargon where possible, and never "
        "overstate certainty."
    ),
    tools=[],
    llm=llm,
    max_iter=ANALYST_MAX_ITER,
    max_rpm=AGENT_MAX_RPM,
    verbose=True,
    allow_delegation=False,
)


reporter = Agent(
    role="Medical Report Writer",
    goal=(
        "Transform the analyst's synthesized insights into a clean, "
        "well-structured report with clear sections, suitable for sharing "
        "with healthcare professionals."
    ),
    backstory=(
        "You are a healthcare communications specialist who writes clear, "
        "structured reports for clinical and administrative audiences. You "
        "use headings, bullet points, and a final summary, and you always "
        "include a brief disclaimer that this is informational, not medical "
        "advice."
    ),
    tools=[],
    llm=llm,
    max_iter=REPORTER_MAX_ITER,
    max_rpm=AGENT_MAX_RPM,
    verbose=True,
    allow_delegation=False,
)