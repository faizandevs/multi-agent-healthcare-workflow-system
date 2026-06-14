"""
Standalone test script.

Run this directly to verify the crew works end-to-end before connecting it
to FastAPI:

    cd backend
    python test_crew.py "What are best practices for reducing ICU readmissions?"

If no argument is given, a default healthcare query is used.

On failure, prints which agent the failure is attributed to (see
crew.CrewExecutionError).
"""

import sys
from dotenv import load_dotenv

from crew import run_crew, CrewExecutionError

load_dotenv()

DEFAULT_QUERY = "What are the best practices for reducing ICU readmission rates?"


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUERY
    print(f"\n=== Running crew for query: {query} ===\n")

    try:
        result = run_crew(query)
    except CrewExecutionError as e:
        print(f"\n=== CREW FAILED ===")
        print(f"Failed agent: {e.failed_agent}")
        print(f"Original error: {e.original_exception}")
        sys.exit(1)

    print("\n=== FINAL REPORT ===\n")
    print(result)


if __name__ == "__main__":
    main()