FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
RUN python -m pip install --upgrade pip && python -m pip install .

RUN addgroup --system kyc && adduser --system --ingroup kyc kyc \
    && mkdir -p /app/data /app/outputs \
    && chown -R kyc:kyc /app

USER kyc
EXPOSE 8000

CMD ["uvicorn", "kyc_platform.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
