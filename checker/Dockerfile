# syntax=docker/dockerfile:1
# vocab-guard checker. Build from the repo root so the word lists are in context:
#   docker build -f checker/Dockerfile -t vocab-guard-checker .

FROM ghcr.io/astral-sh/uv:0.13.5 AS uv

FROM python:3.12.15-slim-trixie AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /src
COPY checker/pyproject.toml checker/uv.lock ./
# Installs SudachiPy and the sudachidict-core dictionary into the venv.
RUN uv sync --frozen --no-dev
# Fail the build if the dictionary doesn't load.
RUN /opt/venv/bin/python -c "from sudachipy import Dictionary; Dictionary(dict='core').create()"

FROM python:3.12.15-slim-trixie
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin checker
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY checker/app ./app
COPY lists/jlpt ./lists/jlpt
COPY lists/sample ./lists/sample
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    VOCAB_GUARD_LISTS=/app/lists
USER checker
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
