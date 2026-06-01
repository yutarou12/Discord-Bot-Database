FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml requirements.txt ./
COPY src ./src

RUN uv pip install --system -r requirements.txt

ENV PYTHONPATH=/app/src

CMD ["python", "-m", "discordbot.main"]
