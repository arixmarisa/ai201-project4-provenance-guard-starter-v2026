
#!/usr/bin/env python3
"""
Provenance Guard — Flask Backend

AI 201 — Project 4
Milestone 4: Multiple Signals and Confidence Scoring

Routes:
    POST /ping       Working example
    POST /submit     Submit text for three-signal analysis
    POST /appeal     Milestone 5
    GET  /log        Read audit log
    GET  /health     Service health information
"""

import uuid

from flask import Flask, jsonify, request

import audit
import config
import detector
import scoring
import stylometry

from repetition import repetition_signal


app = Flask(__name__)


# ============================================================
# Rate Limiting — Unit 8
# ============================================================

class _LimiterOff:
    """
    Placeholder for rate limiting until Unit 8.

    Allows the limiter decorator to remain available
    without enforcing limits.
    """

    def limit(self, *args, **kwargs):
        return lambda view: view


limiter = _LimiterOff()

if config.RATE_LIMITING_ENABLED:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    def rate_limit_key():
        """Identify the creator making a request."""

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
        """Record rate-limit rejections."""

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
# POST /ping — Starter Control
# ============================================================

@app.post("/ping")
def ping():
    """
    Confirm the backend is responding correctly.

    This route is intentionally kept unchanged.
    """

    payload = request.get_json(silent=True) or {}

    return jsonify({
        "ok": True,
        "you_sent": payload.get("message"),
        "service": "provenance-guard",
    })


# ============================================================
# GET /health — Service Status
# ============================================================

@app.get("/health")
def health():
    """Return backend and detector information."""

    loaded = detector._model is not None

    return jsonify({
        "ok": True,
        "detector_model": config.DETECTOR_MODEL,
        "detector_loaded": loaded,
        "rate_limiting": config.RATE_LIMITING_ENABLED,
        "log_entries": len(audit.read_entries()),
    })


# ============================================================
# POST /submit — Milestone 4
# ============================================================

@app.post("/submit")
# @limiter.limit(f"{config.RATE_LIMIT_PER_MINUTE}/minute;{config.RATE_LIMIT_PER_DAY}/day")
def submit():
    """
    Receive writing, analyze it using three independent
    signals, combine the results, and record the decision.

    Milestone 4 Signals:
        1. Language model (50%)
        2. Stylometry (30%)
        3. Repetition (20%) — Stretch Feature

    Expected JSON:
        {
            "text": "Writing to analyze...",
            "creator_id": "writer-001"
        }

    The final reader-facing labels will be implemented
    in Milestone 5.
    """

    # --------------------------------------------------------
    # Step 1: Read JSON request
    # --------------------------------------------------------

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({
            "error": "invalid_json",
            "message": "A valid JSON object is required.",
        }), 400

    text = payload.get("text")
    creator_id = payload.get("creator_id")

    # --------------------------------------------------------
    # Step 2: Validate submitted text
    # --------------------------------------------------------

    if not isinstance(text, str):
        return jsonify({
            "error": "invalid_text",
            "message": "text must be a string.",
        }), 400

    if not text.strip():
        return jsonify({
            "error": "empty_text",
            "message": "text cannot be empty.",
        }), 400

    if len(text) > 20000:
        return jsonify({
            "error": "text_too_long",
            "message": "Text must not exceed 20000 characters.",
        }), 413

    if len(text.split()) < 10:
        return jsonify({
            "error": "text_too_short",
            "message": "Text must contain at least 10 words.",
        }), 400

    # --------------------------------------------------------
    # Step 3: Validate creator ID
    # --------------------------------------------------------

    if (
        not isinstance(creator_id, str)
        or not creator_id.strip()
    ):
        return jsonify({
            "error": "invalid_creator_id",
            "message": "creator_id must be a nonempty string.",
        }), 400

    # --------------------------------------------------------
    # Step 4: Signal 1 — Language Model
    # --------------------------------------------------------

    try:
        model_score = detector.model_signal(text)

    except detector.DetectorUnavailable as exc:
        return jsonify({
            "error": "detector_unavailable",
            "message": str(exc),
        }), 503

    except ValueError as exc:
        return jsonify({
            "error": "invalid_text",
            "message": str(exc),
        }), 400

    # --------------------------------------------------------
    # Step 5: Signal 2 — Stylometry
    # --------------------------------------------------------

    # Measures sentence-length variation,
    # vocabulary diversity, and punctuation density.

    style_score = stylometry.style_signal(text)

    # --------------------------------------------------------
    # Step 6: Signal 3 — Repetition (Stretch Feature)
    # --------------------------------------------------------

    # Measures repeated neighboring word pairs.

    repetition_score = repetition_signal(text)

    # --------------------------------------------------------
    # Step 7: Combine All Three Signals
    # --------------------------------------------------------

    # Uses weights defined in config.py:
    #   Model:      50%
    #   Stylometry: 30%
    #   Repetition: 20%
    #
    # Strong signal disagreement moves the score
    # closer to 0.5 to communicate uncertainty.

    confidence = scoring.combine_signals(
        model_score,
        style_score,
        repetition_score,
    )

    # --------------------------------------------------------
    # Step 8: Create Unique Submission ID
    # --------------------------------------------------------

    content_id = str(uuid.uuid4())

    # --------------------------------------------------------
    # Step 9: Temporary Classification
    # --------------------------------------------------------

    # Milestone 4 calculates real confidence scores.
    # Milestone 5 will convert them into reader-facing
    # labels using scoring.score_to_label().

    guess = "unsure"

    label = (
        "Analysis is incomplete. "
        "Final classification labels are pending."
    )

    status = "decided"

    # --------------------------------------------------------
    # Step 10: Record Decision in Audit Log
    # --------------------------------------------------------

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
    )

    # --------------------------------------------------------
    # Step 11: Return JSON Response
    # --------------------------------------------------------

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
    }), 201


# ============================================================
# POST /appeal — Milestone 5
# ============================================================

@app.post("/appeal")
def appeal():
    """
    Allow writers to appeal a classification.

    This endpoint will be implemented in Milestone 5.

    Expected JSON:
        {
            "content_id": "submission-id",
            "reasoning": "I wrote this myself."
        }
    """

    payload = request.get_json(silent=True) or {}

    return jsonify({
        "error": "not_implemented",
        "message": (
            "POST /appeal is not implemented yet. "
            "This endpoint will be completed in Milestone 5."
        ),
        "you_sent": payload,
    }), 501


# ============================================================
# GET /log — Audit Log
# ============================================================

@app.get("/log")
def get_log():
    """
    Return the most recent audit log entries.

    Example:
        GET /log?limit=10
    """

    limit = request.args.get("limit", type=int)

    entries = audit.read_entries(limit=limit)

    return jsonify({
        "count": len(entries),
        "entries": entries,
    })


# ============================================================
# Start Flask Service
# ============================================================

def main():
    """Launch the Provenance Guard backend."""

    print(f"Provenance Guard on http://{config.HOST}:{config.PORT}")
    print(f"  detector model:  {config.DETECTOR_MODEL}")
    print(
        "  rate limiting:   "
        f"{'ON' if config.RATE_LIMITING_ENABLED else 'off (unit 8)'}"
    )
    print(f"  audit log:       {config.AUDIT_LOG}")
    print()

    print("Check it's alive:")
    print(f'  curl -X POST http://{config.HOST}:{config.PORT}/ping \\')
    print('    -H "Content-Type: application/json" \\')
    print("    -d '{\"message\": \"hello\"}'")
    print()

    # Debug mode is for local development only.
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
    )


if __name__ == "__main__":
    main()
