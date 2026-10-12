FROM python:3.12-slim

# uv, pinned, copied from its official image instead of installed with pip.
COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

# Dependencies first, so code changes don't reinstall everything.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY foreman/ foreman/
RUN uv sync --locked --no-dev

# Run as a normal user. data/ holds the SQLite file and should be a volume.
RUN useradd --create-home app && mkdir -p data && chown app data
USER app

ENV FOREMAN_DB=/app/data/foreman.db
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

# --proxy-headers so the login lockout sees the real client address behind a
# hosting platform's proxy instead of the proxy's.
CMD ["/app/.venv/bin/uvicorn", "foreman.api:create_app", "--factory", \
     "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
