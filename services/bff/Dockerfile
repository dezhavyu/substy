FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/
RUN pip install --upgrade pip && pip install .[dev]
COPY bff_gateway /app/bff_gateway

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app

COPY --from=builder /usr/local /usr/local
COPY --from=builder /app /app

USER app
EXPOSE 8070

CMD ["uvicorn", "bff_gateway.main:app", "--host", "0.0.0.0", "--port", "8070"]
