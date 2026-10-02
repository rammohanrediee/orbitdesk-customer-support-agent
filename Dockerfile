FROM node:22-alpine AS web
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY src/ ./src/
COPY knowledge_base/ ./knowledge_base/
COPY resolved_cases.json sample_outputs.json ./
COPY --from=web /app/frontend/dist/ ./frontend/dist/
RUN pip install --no-cache-dir -e . \
    && useradd --create-home --uid 10001 orbitdesk
USER orbitdesk
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn orbitdesk_support_agent.api:app --host 0.0.0.0 --port 8000"]
