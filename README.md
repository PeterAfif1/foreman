# Foreman

![CI](https://github.com/PeterAfif1/foreman/actions/workflows/ci.yml/badge.svg)

AI lead intake for a small construction business. Customers text, email or chat. Foreman turns that into a clean job card on a Trello-style board, drafts a reply, and gives staff a rough estimate from similar past jobs. A person always reviews and sends.

All demo data is synthetic. No real customer data is in this repo.

## What the AI does

| Part | Job | Result (gpt-4o-mini, 3 runs) |
|---|---|---|
| **Extractor** | Messy message in, structured job out | 97.3% accurate, 1.4% made-up fields |
| **Chat agent** | Collects a job request on `/quote` using tools | 4.0% made-up fields, 0 lost leads, 24/24 attacks blocked |
| **Reply drafts** | Writes the follow-up for a person to send | 77/78 pass every check |
| **Estimates (RAG)** | Finds similar past quotes and gives a price range | 100% of ranges in the right band, declines when there's no data |

The number that matters most: **how often the AI invents something the customer never said.** Full eval history, including the versions that got worse: [docs/EVALS.md](docs/EVALS.md).

## How it's built

- **AI handles language, code handles facts.** Dates, names, prices and "is this chat done" are checked in plain Python, not trusted to the model.
- **Nothing sends automatically.** Every customer-facing message is guarded and reviewed by a person.
- **Every AI call is traced:** cost, tokens, latency and errors per feature.
- **CI blocks bad prompts.** Every push to `main` runs the evals and fails the build if accuracy drops or hallucinations rise ([eval/thresholds.json](eval/thresholds.json)).

## Run it

**1. Set up your keys** (once)

```bash
cp .env.example .env
```

Open `.env` and fill in `OPENAI_API_KEY`, `FOREMAN_PASSWORD` (12+ characters) and `FOREMAN_SECRET_KEY` (any long random string).

**2. Start the app.** Pick one:

**Option A: Docker** (easiest, needs Docker Desktop running)

```bash
docker compose up --build
```

**Option B: Locally** (needs Python, [uv](https://docs.astral.sh/uv/) and Node)

Add `FOREMAN_SECURE_COOKIES=off` to `.env` so login works over plain http, then:

```bash
uv sync
cd web
npm install
npm run build
cd ..
uv run python -m scripts.seed_demo
```

Start the server:

```bash
# Mac / Linux
FOREMAN_DB=data/demo.db uv run uvicorn foreman.api:create_app --factory --reload

# Windows PowerShell
$env:FOREMAN_DB="data/demo.db"; uv run uvicorn foreman.api:create_app --factory --reload
```

**3. Open it**

- Board: http://localhost:8000 (log in with your `FOREMAN_PASSWORD`)
- Customer chat: http://localhost:8000/quote

## Test it

```bash
uv run pytest                                      # 170 tests, free, no API calls
uv run python -m eval.run_eval --label test        # extractor eval (uses OpenAI)
uv run python -m eval.run_chat_eval --label test   # chat agent eval
uv run python -m eval.run_reply_eval --label test  # reply eval
```

## Stack

Python 3.12, OpenAI (structured outputs + tool calling, no agent framework), Pydantic, FastAPI, SQLite, React + Vite + Tailwind, Docker, GitHub Actions.

## Next

- An MCP server exposing the same tools

MIT license
