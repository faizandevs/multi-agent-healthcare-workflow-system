# Backend container — FastAPI + CrewAI
# Build later with: docker build -t healthcare-crew-backend .
# Not required for local development (Phases 1-4 run via uvicorn directly).

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]