# Foreman

![CI](https://github.com/PeterAfif1/foreman/actions/workflows/ci.yml/badge.svg)

A job board for contractors with AI intake. A messy text or email goes in and becomes a job card, with anything the customer didn't say left blank instead of guessed. Cards move through the pipeline like Trello: new lead, contacted, site visit, quote sent, won, in progress, done.

I'm building it for a real small construction business. The demo runs on synthetic leads.

## Example

```
hey saw ur truck on maple st. kitchen redo maybe floors too. under 30k? call 818 555 0142 - dana
```

```json
{
  "is_lead": true,
  "customer_name": "dana",
  "contact": "818 555 0142",
  "job_types": ["kitchen", "flooring"],
  "location": "maple st",
  "budget_max": 30000,
  "urgency": null,
  "missing_info": ["What specific work do you want done in the kitchen?", "What type of flooring are you considering?"]
}
```

Real output from v3, trimmed to the main fields. This run got one thing wrong: "maple st" is where they saw the truck, not where the job is. It does that in about 1 of 3 runs, so the example is in the eval set now.

## Results

27 hand-reviewed leads, 3 runs per version, gpt-4o-mini.

| | Accuracy | Hallucination rate | Cost / lead |
|---|---|---|---|
| v1, prompt only | 96.0% | 5.9% | $0.0002 |
| **v3, prompt + code rules** | **97.3%** | **1.4%** | $0.0002 |

**Hallucination rate** is the number I care about most: how often the model fills in something the customer never said. A blank gets asked about. A made-up budget gets trusted.

Every version, what changed, and why one of them got worse: [docs/EVALS.md](docs/EVALS.md).

## How it works

1. **The model reads the message.** OpenAI structured outputs return a validated `Lead` ([schema.py](foreman/schema.py)), never free text.
2. **Code checks it.** Plain Python handles what models are bad at ([rules.py](foreman/rules.py)): working out whether a deadline is within 60 days, and making sure a name actually appears in the message instead of being guessed from an email address.
3. **The eval scores it** against labels I write by hand before the model sees the example. Every run is saved with the commit, model, prompt version and every prediction ([eval/](eval/)).

## Key decisions

- **Blank beats a guess.** Every field is null unless the message says it.
- **Rules in code, not the prompt.** Asking the model to do date math made scores drop. Having it extract a date and letting Python do the math fixed it.
- **Guesses are allowed if they're labeled.** A name guessed from an email goes in `name_hint`, shown as "maybe".
- **Several runs per version.** Identical runs swung 8 points early on, so no single run counts.
- **No framework.** One structured call needs the OpenAI SDK and Pydantic, nothing else.

## Run it

```bash
uv sync
cp .env.example .env      # add your OpenAI key
uv run pytest             # no API calls
uv run python -m eval.run_eval --label test
```

Or run the board at http://localhost:8000 (API docs at `/docs`). It needs a password and a secret key in `.env` (see `.env.example`):

```bash
cd web && npm install && npm run build && cd ..
uv run python -m scripts.seed_demo     # demo board from the synthetic leads
FOREMAN_DB=data/demo.db uv run uvicorn foreman.api:create_app --factory --reload
```

Working on the board itself? Run `npm run dev` in `web/` for live reload on port 5173. It forwards API calls to port 8000.

Or the production image:

```bash
docker compose up --build
```

Paste a message and it becomes a card in New lead. Open a card to check what the AI pulled out, fix anything wrong, draft a reply that asks for what's missing (you send it yourself), and drag the card along as the job moves. Every fix is recorded: `/api/stats` shows how often each field needed fixing, and `/api/export` turns checked cards into eval data (gitignored, never committed).

## Next

- Real leads from the business (anonymized, never committed)
- Deploy so it works from a phone, then tracing, then RAG over past quotes for rough estimates

MIT license
