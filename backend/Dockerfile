# Development Dockerfile for the Smart Meat backend.
# Uses --reload for hot-reloading during local development.
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install -e ".[dev]"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
