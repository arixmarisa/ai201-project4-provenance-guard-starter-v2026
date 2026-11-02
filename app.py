
#!/usr/bin/env python3
"""
Provenance Guard — Flask Backend

AI 201 — Project 4
Milestone 5: Labels, Appeals, and Verified-Human Demo

Routes:
    POST /ping
    GET  /health
    POST /submit
    POST /appeal
    GET  /content/<content_id>
    POST /verify/start
    POST /verify/complete
    GET  /log

Signals:
    Model:      50%
    Stylometry: 30%
    Repetition: 20%

This is an educational detector, not proof of authorship.
"""

import secrets
import time
import uuid

from flask import Flask, jsonify, request

import audit
import config
import detector
import scoring
import stylometry
from repetition import repetition_signal


app = Flask(__name__)

# In-memory challenges expire after five minutes.
# Successful verification events are saved in the audit log.
verification_challenges = {}


# ============================================================
# Rate Limiting — Unit 8
# ============================================================

class _LimiterOff:
    """No-op limiter until Unit 8."""

    def limit(self, *args, **kwargs):
        return lambda view: view


limiter = _LimiterOff()

if config.RATE_LIMITING_ENABLED:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    def rate_limit_key():
        payload = request.get_json(silent=True)

        if not isinstance(payload, dict):
            return get_remote_address()

        creator = payload.get("creator_id")

        if isinstance(creator, str) and creator.strip():
            return creator

        return get_remote_address()

    limiter = Limiter(
        key_func=rate_limit_key,
        app=app,
        storage_uri=config.RATE_LIMIT_STORAGE,
        default_limits=[],
    )

    @app.errorhandler(429)
    def rate_limited(exc):
        payload = request.get_json(silent=True)

        if not isinstance(payload, dict):
            payload = {}

        audit.log_rejection(
            creator_id=payload.get("creator_id", "unknown"),
            reason="rate_limited",
            limit=str(exc.description),
        )

        return jsonify({
            "error": "rate_limited",
            "message": "Too many submissions. Try again shortly.",
            "limit": str(exc.description),
        }), 429


# ============================================================
# Helpers
# ============================================================

def error_response(message, status=400):
    return jsonify({"error": message}), status


def valid_string(value, maximum=5000):
    """Check that a value is a nonempty bounded string."""
    return (
        isinstance(value, str)
        and bool(value.strip())
        and len(value) <= maximum
    )


def all_audit_entries():
    """Read the append-only audit trail."""
    return audit.read_entries()


def creator_is_verified(creator_id):
    """
    Look for a previously completed demo challenge.

    This checks recorded verification events,
    including events written before server restart.
    """
    return any(
        entry.get("event") == "human_verified"
        and entry.get("creator_id") == creator_id
        for entry in all_audit_entries()
    )


def content_state(content_id):
    """
    Reconstruct a submission's current status.

    Original decisions are preserved. Appeals append
    new events rather than replacing the decision.
    """
    entries = [
        entry for entry in all_audit_entries()
        if entry.get("content_id") == content_id
    ]

    decision = next(
        (
            entry for entry in entries
            if entry.get("status") == "decided"
            and entry.get("combined_score") is not None
        ),
        None,
    )

    if decision is None:
        return None

    appeals = [
        entry for entry in entries
        if entry.get("event") == "appeal"
    ]

    return {
        "content_id": content_id,
        "creator_id": decision["creator_id"],
        "guess": decision["guess"],
        "confidence": decision["combined_score"],
        "label": decision["label"],
        "model_score": decision["model_score"],
        "style_score": decision.get("style_score"),
        "repetition_score": decision.get("repetition_score"),
        "status": "under_review" if appeals else "decided",
        "appeal_count": len(appeals),
        "verified_human": decision.get(
            "verified_human", False
        ),
        "credential": decision.get("credential"),
    }


# ============================================================
# POST /ping — Starter Control
# ============================================================

@app.post("/ping")
def ping():
    payload = request.get_json(silent=True) or {}

    return jsonify({
        "ok": True,
        "you_sent": payload.get("message"),
        "service": "provenance-guard",
    })


# ============================================================
# GET /health
# ============================================================

@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "detector_model": config.DETECTOR_MODEL,
        "detector_loaded": detector._model is not None,
        "rate_limiting": config.RATE_LIMITING_ENABLED,
        "log_entries": len(all_audit_entries()),
    })


# ============================================================
# POST /submit — Final Reader-Facing Labels
# ============================================================

@app.post("/submit")
# @limiter.limit(f"{config.RATE_LIMIT_PER_MINUTE}/minute;{config.RATE_LIMIT_PER_DAY}/day")
def submit():
    """
    Analyze text using the three detection signals.

    Expected JSON:
        {
            "text": "Writing to analyze...",
            "creator_id": "writer-001"
        }
    """

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return error_response(
            "A valid JSON object is required."
        )

    text = payload.get("text")
    creator_id = payload.get("creator_id")

    # Validate the writing.
    if not isinstance(text, str):
        return error_response("text must be a string.")

    if not text.strip():
        return error_response("text cannot be empty.")

    if len(text) > 20000:
        return error_response(
            "Text must not exceed 20000 characters.", 413
        )

    if len(text.split()) < 10:
        return error_response(
            "Text must contain at least 10 words."
        )

    if not valid_string(creator_id, 100):
        return error_response(
            "creator_id must be a nonempty string "
            "of at most 100 characters."
        )

    # Signal 1 — GPT-2 predictability.
    try:
        model_score = detector.model_signal(text)

    except detector.DetectorUnavailable as exc:
        return error_response(str(exc), 503)

    except ValueError as exc:
        return error_response(str(exc), 400)

    # Signal 2 — Writing style.
    style_score = stylometry.style_signal(text)

    # Signal 3 — Repeated word pairs (stretch).
    repetition_score = repetition_signal(text)

    # Milestone 4 combining rule, unchanged.
    confidence = scoring.combine_signals(
        model_score,
        style_score,
        repetition_score,
    )

    # Milestone 5: Replace placeholder labels.
    guess, label = scoring.score_to_label(confidence)

    # Verification is independent of authorship analysis.
    verified = creator_is_verified(creator_id)
    credential = "Verified Human" if verified else None

    content_id = str(uuid.uuid4())
    status = "decided"

    # Preserve the decision and all three signals.
    audit.log_decision(
        content_id=content_id,
        creator_id=creator_id,
        guess=guess,
        model_score=model_score,
        style_score=style_score,
        combined_score=confidence,
        label=label,
        status=status,
        repetition_score=repetition_score,
        verified_human=verified,
        credential=credential,
    )

    return jsonify({
        "content_id": content_id,
        "creator_id": creator_id,
        "guess": guess,
        "confidence": confidence,
        "label": label,
        "model_score": model_score,
        "style_score": style_score,
        "repetition_score": repetition_score,
        "status": status,
        "verified_human": verified,
        "credential": credential,
    }), 201


# ============================================================
# POST /appeal — Milestone 5
# ============================================================

@app.post("/appeal")
def appeal():
    """
    Append an appeal event to the audit log.

    Expected JSON:
        {
            "content_id": "submission-uuid",
            "reasoning": "I wrote this myself."
        }

    The local demo accepts appeals by content ID.
    A real service must authenticate the writer.
    """

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return error_response(
            "A valid JSON object is required."
        )

    content_id = payload.get("content_id")
    reasoning = payload.get("reasoning")

    if not valid_string(content_id, 100):
        return error_response(
            "A valid content_id is required."
        )

    if not valid_string(reasoning, 5000):
        return error_response(
            "reasoning must be nonempty and at most "
            "5000 characters."
        )

    item = content_state(content_id)

    if item is None:
        return error_response("Content not found.", 404)

    if item["status"] == "under_review":
        return error_response(
            "This content is already under review.", 409
        )

    # Append the appeal without changing the original record.
    audit.log_appeal(
        content_id=content_id,
        creator_id=item["creator_id"],
        reasoning=reasoning.strip(),
    )

    return jsonify({
        "content_id": content_id,
        "status": "under_review",
        "message": (
            "Your appeal has been recorded for human review."
        ),
    }), 200


# ============================================================
# GET /content/<id> — Stretch Feature
# ============================================================

@app.get("/content/<content_id>")
def get_content(content_id):
    """
    Return a submission and its current appeal status.
    """

    item = content_state(content_id)

    if item is None:
        return error_response("Content not found.", 404)

    return jsonify(item), 200


# ============================================================
# POST /verify/start — Stretch Feature
# ============================================================

@app.post("/verify/start")
def start_verification():
    """
    Create a five-minute arithmetic challenge.

    This is an educational demonstration.
    It is not proof of real-world human identity.
    """

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return error_response(
            "A valid JSON object is required."
        )

    creator_id = payload.get("creator_id")

    if not valid_string(creator_id, 100):
        return error_response(
            "A valid creator_id is required."
        )

    if creator_is_verified(creator_id):
        return jsonify({
            "creator_id": creator_id,
            "verified_human": True,
            "credential": "Verified Human",
            "message": "Creator already verified.",
        }), 200

    first_number = secrets.randbelow(30) + 10
    second_number = secrets.randbelow(30) + 10
    challenge_id = str(uuid.uuid4())

    verification_challenges[challenge_id] = {
        "creator_id": creator_id,
        "answer": first_number + second_number,
        "expires_at": time.time() + 300,
        "attempts": 0,
    }

    return jsonify({
        "challenge_id": challenge_id,
        "creator_id": creator_id,
        "question": (
            f"What is {first_number} + {second_number}?"
        ),
        "expires_in_seconds": 300,
    }), 201


# ============================================================
# POST /verify/complete — Stretch Feature
# ============================================================

@app.post("/verify/complete")
def complete_verification():
    """
    Evaluate a challenge answer and log successful
    demonstration verification.

    A challenge permits up to three attempts.
    """

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return error_response(
            "A valid JSON object is required."
        )

    challenge_id = payload.get("challenge_id")
    creator_id = payload.get("creator_id")
    answer = payload.get("answer")

    if not isinstance(challenge_id, str):
        return error_response(
            "challenge_id is required."
        )

    challenge = verification_challenges.get(challenge_id)

    if challenge is None:
        return error_response(
            "Challenge not found or already used.", 404
        )

    if time.time() > challenge["expires_at"]:
        del verification_challenges[challenge_id]
        return error_response("Challenge expired.", 410)

    if creator_id != challenge["creator_id"]:
        return error_response(
            "Creator does not match challenge.", 403
        )

    if type(answer) is not int:
        return error_response("answer must be an integer.")

    challenge["attempts"] += 1

    if answer != challenge["answer"]:
        if challenge["attempts"] >= 3:
            del verification_challenges[challenge_id]
            return error_response(
                "Too many incorrect attempts.", 429
            )

        return error_response(
            "Incorrect verification answer.", 400
        )

    del verification_challenges[challenge_id]

    # Record the successful challenge as an audit event.
    # This event is not a writing-classification decision.
    audit.log_decision(
        content_id=f"verification-{uuid.uuid4()}",
        creator_id=creator_id,
        event="human_verified",
        status="verified",
        credential="Verified Human",
        verification_method="arithmetic_challenge",
    )

    return jsonify({
        "creator_id": creator_id,
        "verified_human": True,
        "credential": "Verified Human",
        "message": "Verification challenge completed.",
    }), 200


# ============================================================
# GET /log — Audit Log
# ============================================================

@app.get("/log")
def get_log():
    limit = request.args.get("limit", type=int)
    entries = all_audit_entries()

    if limit is not None:
        entries = entries[-max(limit, 0):] if limit > 0 else []

    return jsonify({
        "count": len(entries),
        "entries": entries,
    })


# ============================================================
# Start Flask Service
# ============================================================

def main():
    print(
        f"Provenance Guard on "
        f"http://{config.HOST}:{config.PORT}"
    )
    print(f"  detector model:  {config.DETECTOR_MODEL}")
    print(
        "  rate limiting:   "
        f"{'ON' if config.RATE_LIMITING_ENABLED else 'off (unit 8)'}"
    )
    print(f"  audit log:       {config.AUDIT_LOG}")
    print()

    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
    )


if __name__ == "__main__":
    main()
