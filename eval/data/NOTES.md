# Labeling notes

Judgment calls, so the same situation gets the same label next time.

- **gen-004 ("call me back" + number):** `is_lead: true`. Someone reaching out to a contractor for a callback is a lead until proven otherwise. Missing every other field is the point of the example.
- **gen-006 (burst pipe):** `job_types: ["repair"]` only. Floor or cabinet damage is likely but not requested, so it goes in `missing_info`, not `job_types`.
- **gen-008 ("budget is flexible"):** `budget` null and `urgency` null. "Flexible" here is about money, not timing. This tests whether the model confuses the two.
- **gen-008 ("right by the high school"):** `location` null. A landmark isn't a city or neighborhood.
- **gen-009 ("next spring"):** `urgency` null. It's a date, but months out, so not "soon", and they never said timing is open, so not "flexible".
- **gen-009 (bedroom + bathroom addition):** `job_types: ["addition"]`. The bathroom is part of the new addition, not a remodel of an existing bathroom.
- **gen-010 (name only in the email address):** `customer_name` null. "carlos.reyes88" isn't the customer saying their name. Filling it is counted as a hallucination.
- **gen-003 ("before we move in"):** `urgency: soon`. A move-in date is a near deadline even without timing words. Changed from null after the v0 review.
- **Deadlines:** `soon` means the deadline is within 60 days of `received_at`. Further out is null. Every row has a `received_at` date so deadline labels can be checked:
  - gen-011 "before Thanksgiving": Thanksgiving is 2026-11-26, 45 days after 2026-10-12, so `soon`.
  - gen-013 "next month": November 2026, at most 50 days out, so `soon`.
  - gen-014 "before the rainy season": LA rain usually starts in November, inside 60 days, so `soon`.
  - gen-012 "a June wedding": June 2027, about 232 days out, so null.
  - gen-009 "next spring": 5+ months after 2026-10-09, so null.
  - gen-003 "before we move in": no date given, but a move-in on a just-bought house is near by nature, so `soon`.
  - Known gap: the extractor doesn't see `received_at` yet, so it can't do this math. The prompt also still says "next few weeks" rather than 60 days.
- **Names in email addresses (gen-012, gen-015, gen-016):** the email never supplies a name. If they sign or introduce themselves, use exactly what they wrote ("Sam", not "Samantha Ortiz"). Same rule as gen-010.
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
