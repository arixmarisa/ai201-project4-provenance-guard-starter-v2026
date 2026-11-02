# Provenance Guard

> **AI 201 — Project 4 · Unit 7**  
> Setup and execution instructions: [RUNNING.md](RUNNING.md).
>
> Start the API with `python app.py`, then send requests to `http://127.0.0.1:5000`.
> Run `python test.py` to check the local development environment.

Provenance Guard is a Flask API that explores patterns associated with AI-generated text. **Its scores are uncalibrated heuristics, not proof of authorship.** A classification must not be used as the sole basis for an accusation or penalty.

---

## What This Does

1. A writer sends `POST /submit` with JSON containing `text` and `creator_id`.
2. `app.py::submit` validates both fields, rejects empty or malformed submissions, requires at least **10 words**, and limits input to **20,000 characters**.
3. `detector.py::model_signal` measures language-model predictability with a local GPT-2 model.
4. `stylometry.py::style_signal` examines sentence lengths, vocabulary diversity, and punctuation; `repetition.py::repetition_signal` measures repeated neighboring word pairs.
5. `scoring.py::combine_signals` calculates the weighted score and moves strongly conflicting results toward uncertainty.
6. `scoring.py::score_to_label` assigns `human`, `unsure`, or `ai` and supplies a non-accusatory explanation.
7. The API generates a UUID `content_id`, logs the original decision to `logs/audit.jsonl`, and returns all three signal values, combined `confidence`, label, status, and the demo verification credential if applicable.
8. A writer can appeal via `POST /appeal`. The decision stays in the audit log, while a separate appeal event changes the **current** status to `under_review`. `GET /content/<id>` reconstructs that status.

| Route | Purpose |
|---|---|
| `POST /ping` | Starter health check |
| `GET /health` | Service and detector status |
| `POST /submit` | Three-signal analysis and final reader-facing label |
| `POST /appeal` | Append a human-review request |
| `GET /content/<id>` | Retrieve decision and current appeal status (stretch) |
| `GET /log?limit=5` | Inspect audit entries |
| `POST /verify/start` | Start a five-minute arithmetic challenge (stretch) |
| `POST /verify/complete` | Complete the challenge and record a demo credential (stretch) |

---

## Signals and Scoring

All signals have values from `0.0` to `1.0`; **larger values represent stronger AI-like patterns, not a measured probability of AI authorship**.

### Signal one — the model signal

**What it measures:** `detector.py::model_signal` uses the GPT-2 language model to estimate predictability of the submitted text.

**Why that might differ between human and AI writing:** Some automatically generated passages use high-frequency, predictable constructions. Predictability provides a perspective different from surface-level stylistic features.

**What it can't see:** Predictable human writing (technical writing, formulaic assignments, common expressions) can score high. Unusual or edited AI writing may score low. A model's training distribution also affects its judgments; predictability does **not** establish authorship.

**Weight:** `0.50`.

### Signal two — the style signal

**What it measures:** `stylometry.py::style_signal` examines sentence-length spread, unique-word ratio (`type_token_ratio`), and selected punctuation marks per word (`punctuation_density`).

**Why that might differ between human and AI writing:** Generated writing can be structurally uniform, while natural writing can show variation in sentence lengths and vocabulary. These are possible correlations, not definitive traits.

**What it can't see:** Formal human writing can be unusually uniform; AI text can be prompted to vary its style. Short samples provide little evidence, and subject matter or language can change these metrics.

**Weight:** `0.30`.

### Signal three — repetition (stretch feature)

**What it measures:** `repetition.py::repetition_signal` counts repeated neighboring **two-word** pairs (bigrams) and normalizes the count to `0.0–1.0`; inputs shorter than ten tokenized words receive a neutral `0.5`.

**Why that might differ between human and AI writing:** Some generation failures produce repeated constructions, providing an additional measurable feature.

**What it can't see:** Human poetry, instructions, or technical prose can repeat phrases. AI-generated text may contain no repetitions whatsoever. Zero repetition does **not** imply human authorship.

**Weight:** `0.20`.

### The combining rule

**Where it lives:** `scoring.py::combine_signals`

**The rule:** A weighted average combines the three 0–1 signals. If the difference between the largest and smallest signal is at least `0.45`, the combined value is moved halfway toward `0.50`. This favors uncertainty rather than a strong accusation when the methods contradict one another.

**The numbers:**

```text
weighted = 0.50 × model_score + 0.30 × style_score + 0.20 × repetition_score
if max(signal_scores) - min(signal_scores) >= 0.45:
    combined = 0.50 + (weighted - 0.50) × 0.50
else:
    combined = weighted
```

Scores are clamped to `0–1` and rounded to four decimal places.

**A case where my signals split, and what the rule does:** My actual campus passage returned `model_score=0.8105`, `style_score=0.6355`, and `repetition_score=0.0`. The model found relatively high predictability, but no repeated bigrams were present. The initial weighted score is:

```text
0.50(0.8105) + 0.30(0.6355) + 0.20(0.0) = 0.5959
```

The spread is `0.8105`, greater than `0.45`, so the disagreement safeguard produces:

```text
0.50 + (0.5959 - 0.50) × 0.50 = 0.5479
```

The API returned **`0.5479` / `unsure`**. This is an example of preferring an inconclusive result over overstating the evidence. The weights and thresholds have **not** been validated against a representative dataset; the false-positive tradeoff requires further evaluation.

---

## Label Variants

`scoring.py::score_to_label` maps the combined score into one of three readable explanations.

| Label | Score range | The exact text a reader sees |
|---|---|---|
| high-confidence human (`human`) | `0.00–0.30`, inclusive | This writing shows patterns associated with human writing. Automated analysis cannot verify who wrote it. |
| unsure (`unsure`) | Greater than `0.30`, less than `0.80` | We cannot reliably determine how this text was written. No conclusion about its authorship should be drawn from this result. |
| high-confidence AI (`ai`) | `0.80–1.00`, inclusive | This writing shows patterns associated with AI-generated text. This is not proof of AI authorship, and the writer may appeal. |

**Why I worded the unsure one this way:** It acknowledges that the signal evidence is inadequate without implying that a person who wrote their own work is dishonest. The word *cannot* explains that uncertainty is a limitation of the detector rather than a statement about the writer.

**Reachability test:** Running `python scoring.py` produced `human` for `0.10` and `0.30`, `unsure` for `0.50`, and `ai` for `0.80` and `0.95`. This verifies the mapping's boundaries, **not** that representative real passages are classified correctly.

---

## Sample Run

These are real local requests and outputs from **November 2, 2026**, against `http://127.0.0.1:5000`. The identifiers and scores below are not fabricated demonstration values.

### A submission

**Request:**

```bash
curl -i -X POST http://127.0.0.1:5000/submit \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Yesterday I walked across campus on my way to class. The weather was colder than I expected, and I realized I had forgotten my jacket. I stopped for coffee before going to the library to finish an assignment.",
    "creator_id": "writer-001"
  }'
```

**Actual response:** `HTTP 201 CREATED`

```json
{
  "confidence": 0.5479,
  "content_id": "25345052-7e9d-4e05-8044-15ea5d27592a",
  "creator_id": "writer-001",
  "credential": null,
  "guess": "unsure",
  "label": "We cannot reliably determine how this text was written. No conclusion about its authorship should be drawn from this result.",
  "model_score": 0.8105,
  "repetition_score": 0.0,
  "status": "decided",
  "style_score": 0.6355,
  "verified_human": false
}
```

### An appeal

**Request:**

```bash
curl -i -X POST http://127.0.0.1:5000/appeal \
  -H "Content-Type: application/json" \
  -d '{
    "content_id": "25345052-7e9d-4e05-8044-15ea5d27592a",
    "reasoning": "I wrote this passage myself and would like a human review of the automated classification."
  }'
```

**Actual response:** `HTTP 200 OK`

```json
{
  "content_id": "25345052-7e9d-4e05-8044-15ea5d27592a",
  "message": "Your appeal has been recorded for human review.",
  "status": "under_review"
}
```

### What the log shows afterwards

**Request:**

```bash
curl "http://127.0.0.1:5000/log?limit=5"
```

The actual response included these **two original entries** (shown as the relevant entries from the larger `entries` array):

```json
[
  {
    "combined_score": 0.5479,
    "content_id": "25345052-7e9d-4e05-8044-15ea5d27592a",
    "creator_id": "writer-001",
    "credential": null,
    "guess": "unsure",
    "label": "We cannot reliably determine how this text was written. No conclusion about its authorship should be drawn from this result.",
    "model_score": 0.8105,
    "repetition_score": 0.0,
    "status": "decided",
    "style_score": 0.6355,
    "timestamp": "2026-11-02T22:07:16+00:00",
    "verified_human": false
  },
  {
    "content_id": "25345052-7e9d-4e05-8044-15ea5d27592a",
    "creator_id": "writer-001",
    "event": "appeal",
    "reasoning": "I wrote this passage myself and would like a human review of the automated classification.",
    "status": "under_review",
    "timestamp": "2026-11-02T22:07:42+00:00"
  }
]
```

The original `decided` decision was **not overwritten**. A distinct `appeal` event was appended.

### Content lookup (stretch)

**Request:**

```bash
curl "http://127.0.0.1:5000/content/25345052-7e9d-4e05-8044-15ea5d27592a"
```

**Actual response:** `HTTP 200 OK`

```json
{
  "appeal_count": 1,
  "confidence": 0.5479,
  "content_id": "25345052-7e9d-4e05-8044-15ea5d27592a",
  "creator_id": "writer-001",
  "credential": null,
  "guess": "unsure",
  "label": "We cannot reliably determine how this text was written. No conclusion about its authorship should be drawn from this result.",
  "model_score": 0.8105,
  "repetition_score": 0.0,
  "status": "under_review",
  "style_score": 0.6355,
  "verified_human": false
}
```

### Verified-human demo (stretch)

**Start request:**

```bash
curl -i -X POST http://127.0.0.1:5000/verify/start \
  -H "Content-Type: application/json" \
  -d '{"creator_id":"writer-001"}'
```

**Actual response:** `HTTP 201 CREATED`

```json
{
  "challenge_id": "aacc42ae-5b0e-4023-a96c-7187f1ef878f",
  "creator_id": "writer-001",
  "expires_in_seconds": 300,
  "question": "What is 16 + 26?"
}
```

**Completion request:**

```bash
curl -i -X POST http://127.0.0.1:5000/verify/complete \
  -H "Content-Type: application/json" \
  -d '{
    "creator_id": "writer-001",
    "challenge_id": "aacc42ae-5b0e-4023-a96c-7187f1ef878f",
    "answer": 42
  }'
```

**Actual response:** `HTTP 200 OK`

```json
{
  "creator_id": "writer-001",
  "credential": "Verified Human",
  "message": "Verification challenge completed.",
  "verified_human": true
}
```

A new submission for `writer-001` then returned the following **actual** response (`HTTP 201 CREATED`):

```json
{
  "confidence": 0.5479,
  "content_id": "d9b9094b-3307-45e9-97f4-2aa2c0ce1f61",
  "creator_id": "writer-001",
  "credential": "Verified Human",
  "guess": "unsure",
  "label": "We cannot reliably determine how this text was written. No conclusion about its authorship should be drawn from this result.",
  "model_score": 0.8105,
  "repetition_score": 0.0,
  "status": "decided",
  "style_score": 0.6355,
  "verified_human": true
}
```

The arithmetic challenge is **not secure human identity verification**; a script could solve it, and `creator_id` is self-declared. This is a course demonstration of a credential workflow only.

### Local environment check

`python test.py` reported **9 passed, 0 failed, 0 to look at, 0 skipped** on Python 3.11.16. This verifies environment readiness, not detector accuracy or the five acceptance criteria.

---

## How I Used AI

### Moment 1 — Design and scoring

- **What I asked for:** Help implementing the second (stylometry) signal, designing a third repetition-based stretch signal, and choosing a rule for combining them.
- **What came back:** Proposed Python implementations for `stylometry.py`, `repetition.py`, `scoring.py`, and signal weights in `config.py`, including a disagreement safeguard.
- **What I changed or verified:** I integrated the implementations, ran direct stylometry and repetition tests, confirmed the weights sum to 1, and checked four scoring cases numerically. I kept the disagreement safeguard because it moved the conflicting campus sample toward uncertainty.

### Moment 2 — Backend, labels, and appeals

- **What I asked for:** Complete Flask routes, reader-friendly labels, appeal tracking, and optional content lookup and verification workflows.
- **What came back:** Code examples and complete file replacements for `scoring.py` and `app.py`, alongside cURL test commands.
- **What I changed or verified:** My first Milestone 5 submission still returned a placeholder label; I corrected `app.py` to call `scoring.score_to_label(confidence)` and resubmitted. I also tested `POST /appeal`, `GET /content/<id>`, `/verify/start`, `/verify/complete`, the follow-up credential-bearing submission, and nine environment checks. I used the actual responses above rather than generated example scores.

**Limits of AI assistance:** AI-generated code and descriptions require local testing. These checks establish that the routes behaved as expected in the tested cases, not that the detector is accurate, equitable, or production-ready.

---

## Planned Stretch Features — Unit 7

The following three stretch features were included in the project plan. Their implementations have been tested locally. The historical order of commits should be checked in Git rather than inferred from this document.

### 1. Third Detection Signal (+1 Point)

**Plan:** Add a repetition-based signal, using 50% model / 30% stylometry / 20% repetition.  
**Implemented:** `repetition.py::repetition_signal` counts repeated bigrams. The test passage repeating “The system works well” produced `1.0`; the natural-writing comparison produced `0.0`. The signal is included in `/submit`, `scoring.py::combine_signals`, and the audit log.

### 2. Content Lookup Endpoint (+1 Point)

**Plan:** Implement `GET /content/<id>` to retrieve classification, confidence, and current review status.  
**Implemented:** The endpoint returned `appeal_count: 1` and `status: under_review` for an appealed submission, while retaining the original recorded decision.

### 3. Verified-Human Credential (+1 Point)

**Plan:** Require a separate challenge and display its completion credential on future submissions.  
**Implemented:** `POST /verify/start` and `POST /verify/complete` awarded a `Verified Human` demo credential, which appeared on a later submission. This does **not** verify a real person or the origin of the submitted text.

---

<!-- ═══════════════════════ UNIT 8 — THE TEST ═══════════════════════ -->

---

## Rate Limiting

**My limits:** ___ per minute, ___ per day

**Why those numbers and not others:**
<!-- Think about two people: a real writer submitting their own work a few
     times an hour, and a script sending a thousand variations to map your
     thresholds. Your numbers have to be liveable for the first and hostile to
     the second. -->

**What a caller counts as:** <!-- per address, or per creator_id? They fail
differently — one script can look like a thousand callers, and one household
can look like one. -->

**The run of status codes when I pushed past it:**

<!-- python run_attacks.py --flood 15 -->

```

```

---

## Attack Run — Before

<!-- Every attack with its outcome and a held-or-broke mark.
     `run_attacks.py --label before` produces the table. -->



**Ten audit log entries from the run**

<!-- Choose entries that show the interesting failures, not the ten easiest. -->

```json

```

**The single worst outcome** — the one I'd least want to explain to a writer
whose work got caught by it:



---

## Run Log and Verdicts

<!-- Your five criteria across three trials. `run_eval.py --label before`. -->

| Criterion | Target | Run 1 | Run 2 | Run 3 | Verdict |
|---|---|---|---|---|---|
| 1.  |  |  |  |  |  |
| 2.  |  |  |  |  |  |
| 3.  |  |  |  |  |  |
| 4.  |  |  |  |  |  |
| 5.  |  |  |  |  |  |

**Real output from one trial**, pasted as text, naming the file and function
that produced it:

```json

```

**Diagnoses**

<!-- For each miss AND each broken attack: the stage and the mechanism.

     Your service has five stages: the route, signal one, signal two, the
     combining rule, and the label mapping.

     Not a diagnosis:  "The evasion attacks got through."
     A diagnosis:      "Four evasion inputs got through. All four had typos
                        added to AI-generated text. My second signal measures
                        word variety, and typos raise word variety — so it read
                        them as more human. My combining rule weights that
                        signal at 0.6, so it dragged the whole score down."

     Look for a pattern. Five failures on one signal is one problem, not five. -->



---

## The Improvement

**What I changed:**

**Which diagnosis pointed at it:**

### Attack Run — After

<!-- Same format. `run_attacks.py --label after` -->



**Did it help, and how do I know:**

<!-- Widening the unsure band usually fixes one problem and creates another.
     Reporting that trade honestly is worth full credit. -->



---

## What's Still Broken

<!-- For each attack still getting through and each criterion still missed:
     what you'd do, and why you stopped. -->



**The trade I'd make if this ran for real:**

<!-- Two sentences. Fewer wrong accusations means more AI text getting through.
     Say which way you'd go and WHO PAYS FOR IT. -->



<!-- ═════════════════════════════════════════════════════════════════════

     SUBMISSION CHECKLIST — unit 7

       [ ] criteria.md has five numbered criteria, each naming a target
       [ ] Each has a reason underneath
       [ ] POST /submit returns content_id, guess, confidence, label,
           model_score and style_score
       [ ] Two signals that measure DIFFERENT things, each with a named blind spot
       [ ] Three label variants, all reachable, written out in full
       [ ] POST /appeal changes status and writes to the log
       [ ] Signals and Scoring names scoring.py::combine_signals
       [ ] Sample Run: a submission AND an appeal, as pasted text
       [ ] At least four new commits
       [ ] Repository URL submitted — WRITE IT DOWN

     SUBMISSION CHECKLIST — unit 8

       [ ] Rate limiting on /submit, with your numbers justified
       [ ] The pasted run of status codes showing 429
       [ ] Audit log with all nine fields, recording rejections too
       [ ] The attack set run IN FULL, every input with an outcome
       [ ] Ten audit log entries pasted as text
       [ ] Five criteria across three trials
       [ ] A diagnosis for every miss and every broken attack — stage AND mechanism
       [ ] One improvement, with Attack Run — After
       [ ] What's Still Broken, including the production trade
       [ ] At least four new commits
       [ ] The SAME repository URL as last unit

     Do not delete and recreate this repository.
     ═════════════════════════════════════════════════════════════════════ -->

---

📖 **How to run this project: [RUNNING.md](RUNNING.md)**
