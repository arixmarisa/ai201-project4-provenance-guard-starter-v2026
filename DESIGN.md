# Provenance Guard — Milestone 1: System Design

## 1. Submission Flow

1. A writer sends their text and creator ID to POST /submit.
2. The backend validates the request and checks for missing or invalid input.
3. The local language model in detector.py analyzes the text for predictability.
4. The stylometry signal in stylometry.py measures sentence variation, vocabulary diversity, and punctuation.
5. The scoring system combines the signals into one AI-likeness score between 0 and 1.
6. The score is converted into one of three reader-facing labels: human, AI, or unsure.
7. The result is assigned a unique content ID, saved in the audit log, and returned as JSON.

## 2. Detection Signals

### Signal 1: Language Model

File: detector.py

Measures how predictable the writing is to a language model.

AI-generated text may sometimes follow patterns that are more predictable than human writing.

Blind spot:
Human writing can also be highly predictable, especially formal, academic, or repetitive writing. The model cannot prove who wrote a passage.

### Signal 2: Stylometry

File: stylometry.py

Measures writing characteristics such as:
- Sentence-length variation
- Vocabulary diversity
- Punctuation density

AI-generated text may sometimes have more uniform writing patterns.

Blind spot:
Human writers can have consistent writing styles, and AI-generated text can be edited to imitate human variation.

## 3. False-Positive Scenario

A student writes an original essay and submits it.

The detector assigns an AI-likeness score of 0.87.

Because the score exceeds the high-confidence AI threshold of 0.80, the writing receives the AI-associated label.

However, the student wrote the essay themselves.

The student can submit an appeal explaining that the writing is original.

The system records the appeal and changes the content status to under_review.

A human reviewer can then evaluate the disagreement rather than treating the detector's output as proof.

This is why the system uses conservative thresholds and an unsure label.

## 4. Endpoint Contracts

### POST /submit

Request:

{
  "text": "The writing to analyze...",
  "creator_id": "writer-001"
}

Response fields:
- content_id: Unique identifier for the submission
- creator_id: Writer's identifier
- guess: human, unsure, or ai
- confidence: Combined AI-likeness score from 0 to 1
- label: Reader-facing explanation
- status: Initially decided

### POST /appeal

Request:

{
  "content_id": "submission-id",
  "reasoning": "I wrote this myself."
}

Response fields:
- content_id: Appealed submission
- status: under_review
- message: Confirmation that the appeal was recorded

## 5. Stretch Features Planned

### Third Signal
Add repetition analysis to measure recurring word pairs.

Planned scoring weights:
- Language model: 50%
- Stylometry: 30%
- Repetition: 20%

### Content Lookup
GET /content/<id> will return an item's current status, scores, and label.

### Verified-Human Path
A writer will complete an additional verification challenge before receiving a Verified Human demonstration credential on future submissions.

This credential will show challenge completion, not proof of authorship.

## 6. Design Priorities

- Minimize false accusations against real writers.
- Return uncertainty rather than forcing a confident decision.
- Preserve original decisions in an audit log.
- Give writers a clear appeal process.
- Keep scoring rules understandable and testable.
