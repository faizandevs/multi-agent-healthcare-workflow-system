"""
Test the /run SSE endpoint directly, without curl.

Run the FastAPI server first:
    uvicorn main:app --reload --port 8000

Then in another terminal:
    python test_api_stream.py "What are best practices for reducing ICU readmission rates?"

If no argument is given, a default healthcare query is used.

Prints each SSE event as it arrives, in real time.
"""

import sys
import json
import requests

DEFAULT_QUERY = "What are the best practices for reducing ICU readmission rates?"
API_URL = "http://localhost:8000/run"


def main():
    query = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUERY
    print(f"POST {API_URL}")
    print(f"query: {query}\n")

    with requests.post(API_URL, json={"query": query}, stream=True) as response:
        response.raise_for_status()

        event_type = None
        for raw_line in response.iter_lines(decode_unicode=True):
            if raw_line is None or raw_line == "":
                continue

            if raw_line.startswith("event:"):
                event_type = raw_line[len("event:"):].strip()
            elif raw_line.startswith("data:"):
                data_str = raw_line[len("data:"):].strip()
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    data = data_str

                print(f"=== event: {event_type} ===")
                if isinstance(data, dict):
                    print(json.dumps(data, indent=2)[:1000])
                else:
                    print(data)
                print()


if __name__ == "__main__":
    main()