# Labeling guide

Labels are written by hand **before** the model sees the example. The model is
never used to produce or "fix" ground truth.

## Row format

One JSON object per line in `eval/data/synthetic.jsonl`:

```json
{"id": "hw-001", "source": "handwritten", "labeled_by": "peter", "received_at": "2026-10-12", "text": "hey saw ur truck on maple st. kitchen redo, maybe floors too. budget under 30k? call 818 555 0142 - dana", "label": {"is_lead": true, "customer_name": "Dana", "contact": "818 555 0142", "job_types": ["kitchen", "flooring"], "location": null, "budget_min": null, "budget_max": 30000, "urgency": null, "scope_summary": "Kitchen remodel, possibly new flooring.", "missing_info": ["Address or neighborhood?", "Timeline?"]}}
```

- `id`: `hw-NNN` for handwritten, `gen-NNN` for generated.
- `source`: `handwritten`, `generated`, or `public`.
- `labeled_by`: who wrote the label.
- `received_at`: the date the message counts as sent. Deadline labels are relative to it.

## Field rules

| Field | Rule |
|---|---|
| `is_lead` | false for spam, wrong numbers, vendor or marketing pitches. When false, every other field is null or `[]`. |
| `customer_name` | As written. A street name or a pet name is not a customer name. |
| `contact` | Only if it is in the text. A sender's number in metadata doesn't count for v1. |
| `job_types` | Every job asked for. "maybe floors too" counts. Use `other` only for real jobs outside the list. |
| `location` | As written. "on maple st" is a street, not a city. Use null unless a city or neighborhood is named. |
| `budget_min` / `budget_max` | "under 30k": max 30000. "at least 10k": min 10000. "about 15k": both 15000. "10 to 15": both bounds. "not sure": null. |
| `urgency` | `emergency`: active damage or safety issue. `soon`: a deadline within 60 days of `received_at`, or an implied near one (a move-in). `flexible`: they say timing is open. Otherwise null. |
| `scope_summary` | 1 to 2 sentences. Not scored yet. |
| `missing_info` | Questions you'd actually ask before quoting. Not scored yet. |

If you aren't sure of a label, the message is ambiguous. Pick a label, then
write down the reasoning in `NOTES.md` so the decision stays the same later.

## What the first 10 should cover

Make them messy. At least one of each:

1. Clear, complete lead (the easy case)
2. Typos and texting shorthand, no punctuation
3. Two jobs in one message
4. "call me back" with a number and nothing else
5. Spam or vendor pitch (`is_lead: false`)
6. Emergency (leak, no power, something collapsed)
7. Budget stated as a range in words ("ten to fifteen grand")
8. Vague location ("near the high school") that should stay null
9. Long rambling message where the job is buried
10. Name and contact that look alike (for example an email that contains a name)
