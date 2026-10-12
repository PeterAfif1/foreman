# Foreman

![CI](https://github.com/PeterAfif1/foreman/actions/workflows/ci.yml/badge.svg)

AI intake for contractors. A messy text or email goes in, structured job details come out, with anything the customer didn't say left blank instead of guessed.

I'm building it for a real small construction business.

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

Or run the API and try it at http://localhost:8000/docs:

```bash
uv run uvicorn foreman.api:app --reload
```

Leads go in as `pending`, get approved as-is or with fixes, and every fix is recorded. `/stats` shows how often each field needed fixing on real messages, and `/export` turns approved leads into eval data (gitignored, never committed).

## Next

- Real leads from the business (anonymized, never committed)
- Approval dashboard where my corrections become new labels
- Deploy, tracing, then RAG over past quotes for rough estimates

MIT license
