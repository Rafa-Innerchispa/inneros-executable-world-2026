FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VOICEOPS_HOST=0.0.0.0 \
    PORT=8080 \
    VOICEOPS_REASONER=synthetic \
    VOICEOPS_ENABLE_LIVE_ASSEMBLYAI=true

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --no-cache-dir .

EXPOSE 8080

CMD ["voiceops-web"]
