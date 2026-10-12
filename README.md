# Foreman

![CI](https://github.com/PeterAfif1/foreman/actions/workflows/ci.yml/badge.svg)

An AI intake agent for contractors. It takes messy inbound leads (texts, emails, call notes), pulls out the job details as structured data, flags what's missing, and drafts a reply for a person to approve.

I'm building it for a real small construction business. Right now it's at the first milestone: extraction plus an eval harness that measures how often the model gets each field right and, more importantly, how often it makes things up.

## The problem

Leads show up like this:

> hey saw ur truck on maple st. kitchen redo maybe floors too. under 30k? call 818 555 0142 - dana

Someone has to read every one, figure out what the job is, and work out what to ask next. Small contractors lose leads because that step gets skipped when they're on site all day.

## How it works

```
lead text ──> extract() ──> Lead (validated JSON) ──> eval vs. hand labels
              OpenAI structured outputs, gpt-4o-mini
```

- **`foreman/schema.py`**: the `Lead` model (Pydantic). If the message doesn't say something, the field is null. There is no "unknown" value and no guessing.
- **`foreman/extract.py`**: sends the text to the model with structured outputs, so the response always parses into a `Lead` or comes back as an explicit refusal. Records tokens, cost and latency for every call.
- **`foreman/prompts.py`**: the prompt, with a version label that goes into every results file.
- **`eval/`**: the dataset, the metrics, and the runner.

## Running it

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env            # add your OpenAI key
uv run pytest                   # unit tests, no API calls
uv run python -m eval.run_eval --label v0
echo "roof is leaking into the kitchen, need someone today" | uv run python -m foreman.extract
```

## How it's evaluated

Every label in `eval/data/` is written by hand **before** the model runs on that example. The model never writes or corrects ground truth. The rules for labeling are in [`eval/data/LABELING.md`](eval/data/LABELING.md).

Each scored field ends up in exactly one bucket:

| Outcome | Meaning |
|---|---|
| correct | both empty, or both filled and matching |
| **hallucination** | model filled it, truth is empty |
| omission | model left it empty, truth is filled |
| wrong | both filled, different values |

The headline number is the **hallucination rate**: hallucinations divided by fields where the truth is empty. A contractor can work with a blank and ask the customer. A made-up budget or address gets trusted and causes real problems.

Also tracked: per-field accuracy, omission rate, lead vs. spam precision and recall, cost per lead, and latency. Every run saves a JSON file in `eval/results/` with the git commit, model, prompt version, a hash of the dataset, and every prediction, so any number in this README can be traced back to the run that produced it.

`scope_summary` and `missing_info` are free text and aren't scored yet.

## Results

| Version | Change | Dataset | Accuracy | Hallucination rate | Cost / lead | Notes |
|---|---|---|---|---|---|---|
| v0 | baseline prompt, gpt-4o-mini | synthetic (n=10), first labels, 1 run | 95.2% | 7.7% | $0.0002 | First run. Review found 1 wrong label (gen-003), fixed before the runs below. |
| v0 | same prompt, rerun | synthetic (n=10), reviewed labels, 3 runs | 95.2% (93.7 to 96.8) | 8.0% (4.0 to 12.0) | $0.00015 | Missed a callback-only lead every run, read "budget is flexible" as timing, tagged a bathroom inside an addition as a remodel. |
| v1 | urgency is timing only; contact requests are leads; rooms in an addition are "addition" | same, 3 runs | 96.8% (all 3) | 4.0% (all 3) | $0.00016 | Fixed all three. Lead recall 88.9% to 100%. New miss: a move-in deadline no longer read as "soon". Still pulls a name out of an email address. [Review](eval/data/NOTES.md#v1-review) |
| v1 | same prompt | synthetic (n=18): 8 new leads on deadlines and names in emails, 3 runs | 96.6% | 6.0% | $0.00016 | New leads caught names copied from email addresses and a June 2027 deadline called "soon". |
| v2 | `name_hint` field, received date sent with each message, 60-day rule and name rules in the prompt | n=18, 3 runs | 93.3% | 12.0% | $0.0002 | **Regression.** Ablations traced it to the long name rule (greetings put in `customer_name`). gpt-4o got names right but cost 16x and did worse overall. Neither model did the date math. [Review](eval/data/NOTES.md#v2-review) |
| v3 | model extracts a `deadline` date; code decides "soon" and checks names appear in the message | n=18, 3 runs | **97.5%** | **2.0%** | $0.0002 | Model alone scores 95.0% / 8.0%; the code rules take it to 97.5% / 2.0%. Names 100%. [Review](eval/data/NOTES.md#v3-review) |

Median latency is about 1.3 s. Ranges are min to max across 3 runs; v0 swung 8 points on hallucination rate between identical runs, which is why every version gets several runs and CI doesn't gate on one. Eighteen examples is still a smoke test, not a benchmark: each field miss moves accuracy about 0.8 points.

## Decisions & Tradeoffs

- **Null over guessing.** One convention for "not stated" across every field. It keeps the schema honest and makes hallucinations easy to count.
- **`job_types` is a list.** Real messages ask for two jobs at once ("kitchen, maybe floors too"). A single field would force the model to drop one.
- **Hallucination and omission rates use different denominators.** You can only hallucinate where the truth is empty, and only omit where it's filled. Dividing both by all fields would hide the rate that matters.
- **Lenient location matching, on purpose.** "Glendale" and "Glendale, CA" are the same answer. It matches whole words, so "LA" doesn't match "Lakewood".
- **Prices are hardcoded.** Cost per lead uses a fixed price table, so old results stay comparable after list prices change.
- **The eval doesn't gate CI yet.** With 10 examples, one flipped field moves accuracy about 10 points, and LLM output varies between runs. CI runs lint and tests on every push and runs the eval on `main`. The score gate comes once the dataset is big enough to be stable.
- **Rules in code, not in the prompt.** v2 tried to make the model do date math and follow "never take a name from an email". It got worse. v3 has the model extract facts (a deadline date, a name) and plain Python decide the rest (days until the deadline, whether the name appears in the message). Each run stores the model's raw answer next to the final one, so the effect of the rules is measured separately.
- **`name_hint` instead of banning guesses.** A name guessed from an email is useful to a contractor, as long as it's shown as a guess. It lives in its own field and doesn't count toward the hallucination rate.
- **No LangChain or agent framework.** For one structured call, the OpenAI SDK and Pydantic are all it takes. Frameworks can come in when there are real tools to orchestrate.

## Roadmap

- [x] Schema, extractor, eval harness
- [ ] Baseline on hand-labeled synthetic leads, then prompt iterations logged above
- [ ] Real leads from the business (anonymized, never committed)
- [ ] FastAPI backend and an approval dashboard, where edits become new labels
- [ ] Docker and cloud deploy
- [ ] RAG over past quotes for rough estimates
- [ ] MCP tools: book a site visit, log a lead
- [ ] Tracing: cost, latency and failure rate per lead

## License

MIT
