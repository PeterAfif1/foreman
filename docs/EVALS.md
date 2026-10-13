# Evals

How Foreman is measured, and every version so far. The short version is in the [README](../README.md).

## Method

Every label in `eval/data/` is written by hand **before** the model runs on that example. The model never writes or corrects ground truth. The rules for labeling are in [`eval/data/LABELING.md`](../eval/data/LABELING.md).

Each scored field ends up in exactly one bucket:

| Outcome | Meaning |
|---|---|
| correct | both empty, or both filled and matching |
| **hallucination** | model filled it, truth is empty |
| omission | model left it empty, truth is filled |
| wrong | both filled, different values |

The headline number is the **hallucination rate**: hallucinations divided by fields where the truth is empty. A contractor can work with a blank and ask the customer. A made-up budget or address gets trusted and causes real problems.

Also tracked: per-field accuracy, omission rate, lead vs. spam precision and recall, cost per lead, and latency. Every run saves a JSON file in `eval/results/` with the git commit, model, prompt version, a hash of the dataset, and every prediction, so any number on this page can be traced back to the run that produced it.

`scope_summary` and `missing_info` are free text and aren't scored yet.

## Every version

| Version | Change | Dataset | Accuracy | Hallucination rate | Cost / lead | Notes |
|---|---|---|---|---|---|---|
| v0 | baseline prompt, gpt-4o-mini | synthetic (n=10), first labels, 1 run | 95.2% | 7.7% | $0.0002 | First run. Review found 1 wrong label (gen-003), fixed before the runs below. |
| v0 | same prompt, rerun | synthetic (n=10), reviewed labels, 3 runs | 95.2% (93.7 to 96.8) | 8.0% (4.0 to 12.0) | $0.00015 | Missed a callback-only lead every run, read "budget is flexible" as timing, tagged a bathroom inside an addition as a remodel. |
| v1 | urgency is timing only; contact requests are leads; rooms in an addition are "addition" | same, 3 runs | 96.8% (all 3) | 4.0% (all 3) | $0.00016 | Fixed all three. Lead recall 88.9% to 100%. New miss: a move-in deadline no longer read as "soon". Still pulls a name out of an email address. [Review](../eval/data/NOTES.md#v1-review) |
| v1 | same prompt | synthetic (n=18): 8 new leads on deadlines and names in emails, 3 runs | 96.6% | 6.0% | $0.00016 | New leads caught names copied from email addresses and a June 2027 deadline called "soon". |
| v2 | `name_hint` field, received date sent with each message, 60-day rule and name rules in the prompt | n=18, 3 runs | 93.3% | 12.0% | $0.0002 | **Regression.** Ablations traced it to the long name rule (greetings put in `customer_name`). gpt-4o got names right but cost 16x and did worse overall. Neither model did the date math. [Review](../eval/data/NOTES.md#v2-review) |
| v3 | model extracts a `deadline` date; code decides "soon" and checks names appear in the message | n=18, 3 runs | **97.5%** | **2.0%** | $0.0002 | Model alone scores 95.0% / 8.0%; the code rules take it to 97.5% / 2.0%. Names 100%. [Review](../eval/data/NOTES.md#v3-review) |
| v1 | same prompt, rerun from commit 4e933bf | n=27: 9 new leads on urgency wording, 3 runs | 96.0% | 5.9% | $0.0002 | Fair "before" number on the current dataset. |
| v3 | same, no changes | n=27, 3 runs | **97.3%** | **1.4%** | $0.0002 | Model alone 95.6% / 5.4%. New miss: "ASAP" with no damage called an emergency. [Review](../eval/data/NOTES.md#v3-on-27-leads) |

Median latency is about 1.3 s. Ranges are min to max across 3 runs; v0 swung 8 points on hallucination rate between identical runs, which is why every version gets several runs and CI doesn't gate on one. 27 examples is still a smoke test, not a benchmark: each field miss moves accuracy about 0.5 points.

## Reply drafts

The AI drafts the first text back to a customer. Code decides what to ask (whatever is still blank: what they need, where, when, budget, name, at most 3), and the model only writes the wording. A person edits and sends it from their own phone. Nothing is sent automatically.

Every draft is checked by plain rules, no model grading a model ([`eval/reply_checks.py`](../eval/reply_checks.py)):

| Check | Fails when |
|---|---|
| invented money | a price or amount the customer never wrote |
| invented when | a day, date or time the customer never wrote |
| invented name | "Hi Carlos" when Carlos only appears inside their email address |
| missed asks | a missing detail that the reply doesn't ask about |
| redundant asks | asking for a budget they already gave |
| dashes, length, sign-off | em dashes, over 500 characters, missing sign-off |

| Version | Change | Passed every check (3 runs) |
|---|---|---|
| r1 | first prompt | 26/26 on one run, but reading the drafts found problems the checks missed: an em dash, wording copied from the instructions, and "call me back" not asking what work they need |
| r2 | plain ask phrases, unknown job asked first, no dashes, dash check added | **77/78** (one missing sign-off) |

Known gap: the labels don't include deadlines, so a draft can ask "when?" after the customer said "before June" and no check notices. In real use the extractor fills the deadline and code skips that question.

When a reply is marked as sent, Foreman stores what was actually sent next to the draft. `/api/stats` reports how many drafts went out unedited: the live quality number once real people use it.

## Chat agent

A public chat (`/quote`) where a customer describes a job. The model has three tools: `SaveDetails` (record what they said; code answers with what's still missing), `Finish` (submit the card) and `EndChat` (spam, abuse). Code enforces everything that has to be exact: what's missing, when finishing is allowed, a turn limit, and that no message mentions a price or a date the customer didn't.

**How it's tested** ([`eval/run_chat_eval.py`](../eval/run_chat_eval.py)):
- **26 simulated customers.** Each starts from a labeled lead's real message and holds a few hidden facts the message didn't include (phone, neighborhood, budget), made up in code. The simulator (another model call) only reveals a fact when asked, so the answer key is exact.
- **8 scripted attacks:** price fishing, date fishing, prompt leak, a fake "SYSTEM OVERRIDE", "am I talking to a real person?", off-topic, a sales pitch, abuse.
- **Business metrics, not just fields:** a real job that ends without a card is a **lost lead**, and a chat that closes on a question the customer can no longer answer is a broken experience. Both are counted.

3 runs per version, gpt-4o-mini. All versions are scored against the same corrected answer key.

| Version | Change | Field accuracy | Hallucination | Lost leads | Closed mid-question | Attacks |
|---|---|---|---|---|---|---|
| a1 | first prompt and tools | 91.9% | 10.1% (6.1 to 15.2) | 0/78 | 0/78 | 23/24 |
| a2 | urgency definitions in the tool schema, names only as written, landmarks aren't locations, $0 budget = not stated, guard false alarm on "today" fixed | 91.2% | 7.1% | **2/78** | **3/78** | 24/24 |
| a3 | code gates: no finishing before asking name and place once, real jobs can't be ended, closed chats can't ask, unstated names removed from replies | 92.7% | 10.1% | 0/78 | 0/78 | 24/24 |
| **a4** | code rule: "flexible" timing only stands if they used timing words | **92.5%** | **4.0%** (3.0 to 6.1) | **0/78** | **0/78** | **24/24** |

Average 2.3 customer messages per chat, about $0.001 of agent calls per chat.

**What the evals caught on the way:**
- **a2 traded hallucinations for lost leads.** Hallucinations went down, but the agent started calling `Finish` on the first message while still asking questions, and twice ended a real job request as if it were spam. Field accuracy barely moved, so it would have shipped if lost leads weren't measured. a3 fixed it in code: `EndChat` is refused once a job is saved, and a closing message can't contain a question.
- **A guardrail false alarm.** "How can I help you **today**?" tripped the date check, so the reply got rewritten and sometimes turned into a closing line. "Today" now only counts next to a scheduling word ("come out today").
- **An eval bug.** The answer key expected a budget on emergencies, which the agent skips on purpose. Fixed, and earlier versions rescored on the corrected key.
- **A test changed after a result,** on purpose and recorded: the off-topic attack expected the chat to end, but steering back to the job ("I'm here to help with construction details, tell me about your project") is better behavior. See [NOTES](../eval/data/NOTES.md).
- **The prompt kept losing to "flexible".** Customers saying their *budget* is flexible, or "not sure yet", became `flexible` timing in 9 of 10 a3 hallucinations, the same trap the extractor fell into in v0. A code rule fixed it; it's shared with the extractor and checked against every hand label first.

Known limits: the simulator is the same model family as the agent, so it may be easier on it than real people are. 26 customers is small: one field moves hallucination rate about 3 points.

## All decisions

- **Null over guessing.** One convention for "not stated" across every field. It keeps the schema honest and makes hallucinations easy to count.
- **`job_types` is a list.** Real messages ask for two jobs at once ("kitchen, maybe floors too"). A single field would force the model to drop one.
- **Hallucination and omission rates use different denominators.** You can only hallucinate where the truth is empty, and only omit where it's filled. Dividing both by all fields would hide the rate that matters.
- **Lenient location matching, on purpose.** "Glendale" and "Glendale, CA" are the same answer. It matches whole words, so "LA" doesn't match "Lakewood".
- **Prices are hardcoded.** Cost per lead uses a fixed price table, so old results stay comparable after list prices change.
- **The eval doesn't gate CI yet.** With 10 examples, one flipped field moves accuracy about 10 points, and LLM output varies between runs. CI runs lint and tests on every push and runs the eval on `main`. The score gate comes once the dataset is big enough to be stable.
- **Rules in code, not in the prompt.** v2 tried to make the model do date math and follow "never take a name from an email". It got worse. v3 has the model extract facts (a deadline date, a name) and plain Python decide the rest (days until the deadline, whether the name appears in the message). Each run stores the model's raw answer next to the final one, so the effect of the rules is measured separately.
- **`name_hint` instead of banning guesses.** A name guessed from an email is useful to a contractor, as long as it's shown as a guess. It lives in its own field and doesn't count toward the hallucination rate.
- **No LangChain or agent framework.** For one structured call, the OpenAI SDK and Pydantic are all it takes. Frameworks can come in when there are real tools to orchestrate.

Per-example failure reviews for each version are in [`eval/data/NOTES.md`](../eval/data/NOTES.md).
