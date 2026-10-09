# Labeling notes

Judgment calls, so the same situation gets the same label next time.

- **gen-004 ("call me back" + number):** `is_lead: true`. Someone reaching out to a contractor for a callback is a lead until proven otherwise. Missing every other field is the point of the example.
- **gen-006 (burst pipe):** `job_types: ["repair"]` only. Floor or cabinet damage is likely but not requested, so it goes in `missing_info`, not `job_types`.
- **gen-008 ("budget is flexible"):** `budget` null and `urgency` null. "Flexible" here is about money, not timing. This tests whether the model confuses the two.
- **gen-008 ("right by the high school"):** `location` null. A landmark isn't a city or neighborhood.
- **gen-009 ("next spring"):** `urgency` null. It's a date, but months out, so not "soon", and they never said timing is open, so not "flexible".
- **gen-009 (bedroom + bathroom addition):** `job_types: ["addition"]`. The bathroom is part of the new addition, not a remodel of an existing bathroom.
- **gen-010 (name only in the email address):** `customer_name` null. "carlos.reyes88" isn't the customer saying their name. Filling it is counted as a hallucination.
- **Single number budgets:** "around $25,000" sets min and max both to 25000 (gen-001).
