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
