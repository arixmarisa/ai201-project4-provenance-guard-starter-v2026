
# Acceptance criteria — Provenance Guard

Five criteria that say what "working" means for this service, written in Unit 7
**before** building and evaluating the completed system.

These criteria prioritize protecting human writers from false accusations,
communicating uncertainty, and making the system reliable and transparent.

---

## 1. Limit false accusations against human writers

**Target:** Of 20 independently human-written samples, no more than 1
may receive a high-confidence AI label in any of the three evaluation trials.

**How to test:** Submit the same 20 human-written passages through
`POST /submit` in three separate trials. Each passage must contain at least
30 words. Record the label returned for every submission. The criterion
passes only if each trial contains at most 1 high-confidence AI label.

**Why this target:**

Falsely accusing a human writer of using AI can damage their credibility.
I chose a maximum false-positive rate of 5% because wrongly accusing
someone is more harmful than failing to recognize some AI-generated text.
The system should favor uncertainty over making an unsupported accusation.

---

## 2. Separate human and AI-generated writing scores

**Target:** The average AI-likeness score of 10 AI-generated passages
must be at least 0.15 higher than the average score of 10 human-written
passages in each of three evaluation trials.

**How to test:** Collect 10 human-written passages and 10 AI-generated
passages, each containing at least 30 words. Submit all 20 passages
through `POST /submit` in each trial. Calculate the average confidence
score for both groups and subtract the human average from the AI average.
The criterion passes if the difference is at least 0.15 in all three trials.

**Why this target:**

The scoring system is designed to combine multiple signals rather than
rely entirely on one detector. A difference of at least 0.15 would show
that the signals provide some meaningful separation between the groups.
This is a realistic target without expecting perfect AI detection.

---

## 3. Ensure all three classification labels are reachable

**Target:** All 101 scores from 0.00 through 1.00, in increments of
0.01, must map to exactly one of the three labels: human, unsure, or AI.
All three labels must appear, and there must be zero classification errors
in each of the three evaluation trials.

**How to test:** Call `scoring.score_to_label()` with scores from 0.00
to 1.00 in increments of 0.01. Verify that every score produces exactly
one valid label. Confirm that a score of 0.20 receives the human label,
0.50 receives the unsure label, and 0.90 receives the AI label. Repeat
the test in three trials.

**Why this target:**

The unsure label is essential because the system cannot confidently
determine authorship in every situation. Every possible score should
produce a predictable and understandable result. Requiring all three
labels to be reachable prevents the system from forcing uncertain
writing into a human or AI category.

---

## 4. Record appeals and update submission status

**Target:** All 10 valid appeals must successfully change their
submission status to `under_review` and create exactly one appeal
entry in the audit log, with zero original decisions lost, in each
of the three evaluation trials.

**How to test:** Submit 10 valid writing samples and record their
`content_id` values. Send one `POST /appeal` request for each submission,
including a nonempty explanation. Use `GET /content/<id>` to confirm
that all 10 submissions have the status `under_review`. Check the audit
log to verify that every original submission remains recorded and
each appeal has exactly one additional entry. Repeat for three trials
using fresh submissions.

**Why this target:**

Because AI detection can incorrectly classify genuine writing, every
writer needs a reliable way to challenge a result. I chose a 100%
success target because an appeal is a basic system function, not a
prediction. Losing an appeal or failing to update its status could leave
an incorrect accusation unresolved.

---

## 5. Reject invalid submissions without crashing

**Target:** All 10 predefined invalid submission requests must return
an HTTP 4xx response, with zero HTTP 5xx errors and zero completed
content decisions created, in each of the three evaluation trials.

**How to test:** Send these 10 invalid requests to `POST /submit`:

1. A request without a JSON body.
2. A JSON array instead of an object.
3. A request missing the `text` field.
4. A request with `text` set to `null`.
5. A request with an empty `text` string.
6. A request containing only whitespace.
7. A request containing fewer than 10 words.
8. A request missing `creator_id`.
9. A request with an empty `creator_id`.
10. A request containing more than 20,000 characters.

For each request, verify that the service returns an HTTP status
between 400 and 499 and does not create a completed classification.
After all 10 requests, send a valid request to confirm the service
is still responsive. Repeat this process in all three trials.

**Why this target:**

Invalid input should never crash the backend or result in misleading
classifications. The 10-word minimum reduces unreliable predictions
from extremely short passages, while the 20,000-character limit
prevents excessive processing by the local language model. I chose
a 100% success target because validating input should be predictable
and reliable.

---

<!--
UNIT 8 — Acceptance Criteria Revision Guidelines

Keep these original criteria unchanged when evaluating the system
in Unit 8.

If a criterion cannot be measured because it is ambiguous or
incorrectly defined, add a clearly labeled revision underneath
the original criterion and explain why it was necessary.

Do not lower a numerical target simply because the system failed
to meet it.

Record the actual results across all three trials, investigate
failures, and document attempted improvements.

Missing an ambitious target is acceptable. The goal is to
evaluate the system against standards established before testing.
-->
