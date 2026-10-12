# Labeling notes

Judgment calls, so the same situation gets the same label next time.

- **gen-004 ("call me back" + number):** `is_lead: true`. Someone reaching out to a contractor for a callback is a lead until proven otherwise. Missing every other field is the point of the example.
- **gen-006 (burst pipe):** `job_types: ["repair"]` only. Floor or cabinet damage is likely but not requested, so it goes in `missing_info`, not `job_types`.
- **gen-008 ("budget is flexible"):** `budget` null and `urgency` null. "Flexible" here is about money, not timing. This tests whether the model confuses the two.
- **gen-008 ("right by the high school"):** `location` null. A landmark isn't a city or neighborhood.
- **gen-009 ("next spring"):** `urgency` null. It's a date, but months out, so not "soon", and they never said timing is open, so not "flexible".
- **gen-009 (bedroom + bathroom addition):** `job_types: ["addition"]`. The bathroom is part of the new addition, not a remodel of an existing bathroom.
- **gen-010 (name only in the email address):** `customer_name` null, `name_hint` "Carlos Reyes". Before v2 there was no hint field, so filling the name counted as a hallucination.
- **gen-003 ("before we move in"):** `urgency: soon`. A move-in date is a near deadline even without timing words. Changed from null after the v0 review.
- **Deadlines:** `soon` means the deadline is within 60 days of `received_at`. Further out is null. Every row has a `received_at` date so deadline labels can be checked:
  - gen-011 "before Thanksgiving": Thanksgiving is 2026-11-26, 45 days after 2026-10-12, so `soon`.
  - gen-013 "next month": November 2026, at most 50 days out, so `soon`.
  - gen-014 "before the rainy season": LA rain usually starts in November, inside 60 days, so `soon`.
  - gen-012 "a June wedding": June 2027, about 232 days out, so null.
  - gen-009 "next spring": 5+ months after 2026-10-09, so null.
  - gen-003 "before we move in": no date given, but a move-in on a just-bought house is near by nature, so `soon`.
  - Known gap: the extractor doesn't see `received_at` yet, so it can't do this math. The prompt also still says "next few weeks" rather than 60 days.
- **Names in email addresses:** `customer_name` is only what they wrote ("Sam", never "Samantha Ortiz"). A name the email suggests goes in `name_hint` when it adds something: gen-010 "Carlos Reyes", gen-012 "K. Oduya", gen-015 "Jenny Park", gen-016 "Samantha Ortiz" (fuller than "Sam"). No hint when the email only repeats the name they gave (gen-001 robert.chen, gen-013 mellison).
- **gen-013 (cracked kitchen floor tiles):** `job_types: ["flooring"]`, not `kitchen`. It's floor work that happens to be in a kitchen.
- **gen-014 (drainage and grading):** `other`. Not a category we have.
- **Single number budgets:** "around $25,000" sets min and max both to 25000 (gen-001).

## v0 failure review

Run `eval/results/20261009-153721_v0.json` (gpt-4o-mini, prompt v0).

| ID | What happened | Verdict |
|---|---|---|
| gen-008 | "budget is flexible" became `urgency: flexible` | **Model error.** The exact trap the example was written for. Fix in the prompt: urgency only comes from timing words. |
| gen-004 | "call me back 3105550144" marked `is_lead: false`, but the number was still extracted | **Model error, and it contradicts the prompt** (non-leads should have every field empty). Decided: a bare callback request is a lead (missing a customer costs more than calling a wrong number). Added to the prompt in v1. |
| gen-003 | "before we move in" became `urgency: soon` | **Label was wrong.** Relabeled to `soon` (a move-in date is a near deadline). |
| gen-009 | `job_types: [addition, bathroom]` vs. label `[addition]` | **Kept the label.** Rule: rooms built as part of new construction are `addition`; `bathroom` means work on an existing bathroom. Added to the prompt in v1. |

Takeaway: half of the misses come from labeling rules that weren't pinned down, not from the model. Fix the labels first, then the prompt, then rerun as v1.

## v1 review

Prompt v1 vs. v0, 3 runs each on the reviewed labels (`eval/results/*_v0-r*.json`, `*_v1-r*.json`).

The v1 rules are written in general terms on purpose. They don't quote any test example, so the gains aren't the model memorizing the eval set.

| ID | v0 (3 runs) | v1 (3 runs) |
|---|---|---|
| gen-004 callback only | not a lead, 3/3 | **fixed** |
| gen-008 "budget is flexible" | urgency `flexible`, 3/3 | **fixed** |
| gen-009 bath inside addition | `[addition, bathroom]`, 3/3 | **fixed** |
| gen-008 landmark as location | "by the high school", 1/3 | fixed |
| gen-003 "before we move in" | correct (`soon`) | **regressed** to null, 3/3 |
| gen-010 name from email address | "Carlos Reyes", 2/3 | "Carlos Reyes", 3/3 |

v1 is also stable: identical scores on all 3 runs, where v0 ranged 93.7% to 96.8%.

Open for v2:
- **gen-003:** the "timing only" rule made the model stricter, so an implied deadline now reads as no timing. It's a trade between the two urgency failures.
- **gen-010:** decide whether a name inside an email address counts. If not, the prompt needs a rule. If yes, relabel it. Either way it's a labeling decision first.
- Both are single examples. Writing a few more leads for each case before tuning again would avoid fitting the prompt to one message.

## v2 review

18 leads, 3 runs per row. v2 added `name_hint`, the received date in each message, a 60-day rule for `soon`, and a rule that names come only from what the person wrote.

| Run | Accuracy | Hallucination | Name hint | Cost / lead |
|---|---|---|---|---|
| v1, gpt-4o-mini | **96.6%** | **6.0%** | n/a | $0.00016 |
| v2, gpt-4o-mini | 93.3% | 12.0% | 88.2% | $0.0002 |
| v2 with date removed (ablation) | 93.3% | 14.0% | 82 to 88% | |
| v2 with a one-line name rule (ablation) | 95.8% | 8.0% | 94.1% | |
| v2, gpt-4o | 92.4% | 4.0% | 94.1% | $0.0032 |

What the ablations showed:
- **The long name rule caused the regression,** not the date. With it, gpt-4o-mini put greetings and phrases in `customer_name` ("hi", "Our daughter's wedding"). A one-line rule removed those.
- **gpt-4o-mini still copies the start of an email address into `customer_name`** ("carlos", "jenny") even when told not to. gpt-4o doesn't (100% on names) but misses more urgency and job types, and costs 16x more.
- **Neither model does the 60-day math reliably.** Both call a June 2027 wedding `soon` with the received date right in the message.
- Results were identical across runs at temperature 0 for every config, so these are real differences, not noise.

Takeaway: two of the remaining failures are things code does better than a model. Date math is a subtraction, and "is this name just the email's local part" is a string check. The next step is moving them out of the prompt: have the model extract the deadline as a date and compute `soon` in code, and check names against the email in code.

## v3 review

v3 moves the two things models did badly into code (`foreman/rules.py`):
- The model extracts a `deadline` as a date. Code sets `soon` if it's within 60 days of `received_at`, and clears `soon` if it's further out or already past.
- `customer_name` has to appear in the message, outside any email address. If it doesn't, it moves to `name_hint`.

3 runs, 18 leads, identical every run:

| | Accuracy | Hallucination | Omission |
|---|---|---|---|
| v1 | 96.6% | 6.0% | 1.4% |
| v3, model output only | 95.0% | 8.0% | |
| **v3, with rules** | **97.5%** | **2.0%** | 2.9% |

Fixed: names copied from emails (gen-010, gen-015), the June 2027 wedding (gen-012, the model gave 2027-06-01 and code cleared `soon`).

Still wrong:
- **gen-003** "before we move in": no date, so the rule can't help. Model says null.
- **gen-008** "budget is flexible" read as timing again. v1 had fixed this; the reworded urgency rule brought it back.
- **gen-016** "nothing urgent" not read as `flexible`. New miss.
- **gen-013** `name_hint` "mellison" from mellison@gmail.com when the full name was signed. Hint only, not in totals. A code rule could drop hints that just repeat customer_name.

Next: these are wording problems in the urgency rule, each from one example. Write more urgency examples (open timing in different words, money words that sound like timing) before touching the prompt again.
