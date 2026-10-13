# Foreman

![CI](https://github.com/PeterAfif1/foreman/actions/workflows/ci.yml/badge.svg)

AI intake for contractors, built for a small construction business. Three AI components, each with its own evals: an **extractor** that turns messy texts into structured jobs, a **customer chat agent** that collects a job request using tools, and **reply drafting**. They feed a Trello-style job board.

The demo runs on synthetic leads I reviewed and labeled by hand. No customer data is in this repo.

## The AI parts

| Component | What it does | How it's tested | Result (3 runs, gpt-4o-mini) |
|---|---|---|---|
| **Extractor** | Message in, validated `Lead` out (structured outputs), then code rules | 27 hand-labeled leads | **97.3%** field accuracy, **1.4%** hallucination (from 96.0% / 5.9%) |
| **Chat agent** | Multi-turn web chat with 3 tools; code gates and output guardrails | 26 simulated customers with hidden facts + 8 attacks | **4.0%** hallucination (from 10.1%), **0** lost leads, **24/24** attacks blocked |
| **Reply drafts** | Code picks what to ask, the model writes it, a person sends it | Rule checks on every draft | **77/78** drafts pass every check |

**Hallucination rate** is the number I watch most: how often the AI fills in something the customer never said. A blank gets asked about. A made-up budget gets trusted.

Full history of every version, including the ones that got worse: [docs/EVALS.md](docs/EVALS.md).

## How it works

```
text / email / call notes ──> extractor ──┐
                                          ├──> code rules ──> card on the board ──> person checks it
customer on /quote ──> chat agent ────────┘        │                                      │
        (tools: SaveDetails, Finish, EndChat)       │                         draft reply, they send it
                                                    └── deadline math, names must appear in the text,
                                                        "flexible" needs timing words, $0 = not stated
```

- **The model handles language; code handles anything exact.** Date math, whether a name really appears in the message, when a chat may finish, and whether a reply mentions a price or date the customer never said are all decided in plain Python ([rules.py](foreman/rules.py), [guards.py](foreman/guards.py), [agent.py](foreman/agent.py)). Every eval stores the model's raw answer next to the final one, so the effect of the rules is measured, not assumed.
- **Guardrails on every customer-facing message.** A reply that mentions a price or date the customer didn't gets one rewrite, then a safe fallback.
- **Nothing is sent automatically.** The chat only collects details; replies are drafted for a person to edit and send.

## What the evals caught

- **Prompt fixes that made things worse.** Extractor v2 doubled hallucinations; ablations traced it to one prompt rule. Chat agent a2 cut hallucinations but started losing real leads, which only showed up because lost leads are measured, not just field accuracy.
- **My own bugs.** A guardrail that flagged "how can I help you *today*", an answer key that expected budgets the agent skips on purpose, a check whose regex never matched "Hi Carlos". Each one fixed and re-measured.
- **The same trap twice.** "Budget is flexible" became flexible *timing* in both the extractor and the agent. Prompts kept losing; a 10-line code rule fixed both.

## Example

```
hey saw ur truck on maple st. kitchen redo maybe floors too. under 30k? call 818 555 0142 - dana
```

```json
{
  "customer_name": "dana",
  "contact": "818 555 0142",
  "job_types": ["kitchen", "flooring"],
  "location": "maple st",
  "budget_max": 30000,
  "urgency": null
}
```

Real extractor output, trimmed. This run got one thing wrong: "maple st" is where they saw the truck, not the job. It does that in about 1 of 3 runs, so the example is in the eval set.

## Run it

```bash
uv sync
cp .env.example .env              # OpenAI key, plus a password and secret key for the app
uv run pytest                     # 170 tests, no API calls
uv run python -m eval.run_eval --label test          # extractor eval
uv run python -m eval.run_chat_eval --label test     # chat agent eval
uv run python -m eval.run_reply_eval --label test    # reply eval
```

The app (board at http://localhost:8000, customer chat at `/quote`):

```bash
cd web && npm install && npm run build && cd ..
uv run python -m scripts.seed_demo
FOREMAN_DB=data/demo.db uv run uvicorn foreman.api:create_app --factory --reload
```

Or `docker compose up --build`.

## Stack

Python 3.12, OpenAI (structured outputs and tool calling, no agent framework), Pydantic, FastAPI, SQLite, React + Vite + Tailwind, Docker, GitHub Actions (tests, front-end and Docker builds, and the extractor eval on `main`).

## Next

- Tracing: cost, latency and failures per AI call
- RAG over past quotes for rough estimates
- An MCP server exposing the same tools
- A CI gate that fails the build if hallucinations go up

MIT license
