
"""
Provenance Guard — Scoring System

Milestone 4:
    Combine three detection signals into one AI-likeness score.

Milestone 5:
    Convert the score into a reader-facing classification.

The combining rule is located in:
    scoring.py::combine_signals

Signals:
    1. Language model (50%)
    2. Stylometry (30%)
    3. Repetition (20%) — Stretch Feature

Higher scores indicate more AI-like writing patterns.

These scores are heuristics and do not prove authorship.
"""

import math
import config


# ── Helper ───────────────────────────────────────────────────

def clamp(value: float) -> float:
    """Keep a number between 0.0 and 1.0."""
    return max(0.0, min(1.0, float(value)))


# ── Combining the signals — Milestone 4 ─────────────────────

def combine_signals(
    model_score: float,
    style_score: float,
    repetition_score: float = 0.5,
) -> float:
    """
    Combine three signals into one score between 0 and 1.

    Higher scores indicate more AI-like writing patterns.

    Signal weights:
        Model:      50%
        Stylometry: 30%
        Repetition: 20%

    Formula:
        combined = (
            0.50 * model_score
            + 0.30 * style_score
            + 0.20 * repetition_score
        )

    Disagreement handling:
        If the difference between the highest and lowest
        signal is at least 0.45, move the combined score
        halfway toward 0.50.

    Example:
        Model = 0.90
        Style = 0.20
        Repetition = 0.10

        Weighted score = 0.53
        Adjusted score = 0.515

    The default repetition_score=0.5 preserves compatibility
    with existing code that passes only two signals.
    """

    values = [
        float(model_score),
        float(style_score),
        float(repetition_score),
    ]

    # Reject invalid numerical values.
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Signal scores must be finite numbers.")

    model, style, repetition = map(clamp, values)

    # Weighted combination.
    combined = (
        config.WEIGHT_MODEL_SIGNAL * model
        + config.WEIGHT_STYLE_SIGNAL * style
        + config.WEIGHT_REPETITION_SIGNAL * repetition
    )

    # Detect strong disagreement.
    disagreement = max(values) - min(values)

    if disagreement >= config.DISAGREEMENT_THRESHOLD:
        combined = (
            0.5
            + (combined - 0.5) * config.DISAGREEMENT_SHRINK
        )

    return round(clamp(combined), 4)


# ── Labels — Milestone 5 ─────────────────────────────────────

def score_to_label(score: float) -> tuple[str, str]:
    """
    Convert a score into a guess and reader-facing label.

    Milestone 5 will replace the placeholder text
    with three complete reader-friendly labels.

    Returns:
        (guess, label_text)
    """

    if score >= config.AI_THRESHOLD:
        return (
            "ai",
            "PLACEHOLDER — write the high-confidence AI label.",
        )

    if score <= config.HUMAN_THRESHOLD:
        return (
            "human",
            "PLACEHOLDER — write the high-confidence human label.",
        )

    return (
        "unsure",
        "PLACEHOLDER — write the unsure label.",
    )


# ── Label Ranges ─────────────────────────────────────────────

def label_ranges() -> list[tuple[str, str]]:
    """
    Return the score range for each label.

    Uses thresholds from config.py to prevent
    documentation and implementation from drifting apart.
    """

    return [
        (
            "high-confidence human",
            f"0.00 through {config.HUMAN_THRESHOLD:.2f} (inclusive)",
        ),
        (
            "unsure",
            f"above {config.HUMAN_THRESHOLD:.2f} "
            f"and below {config.AI_THRESHOLD:.2f}",
        ),
        (
            "high-confidence AI",
            f"{config.AI_THRESHOLD:.2f} through 1.00 (inclusive)",
        ),
    ]


# ── Terminal Testing ────────────────────────────────────────

if __name__ == "__main__":
    print("Provenance Guard — Milestone 4 Scoring")
    print()

    examples = [
        (0.10, 0.20, 0.10),
        (0.50, 0.50, 0.50),
        (0.90, 0.90, 0.90),
        (0.90, 0.20, 0.10),
    ]

    for model, style, repetition in examples:
        result = combine_signals(
            model,
            style,
            repetition,
        )

        print(
            f"Model={model:.2f}, "
            f"Style={style:.2f}, "
            f"Repetition={repetition:.2f} "
            f"-> Combined={result:.4f}"
        )

    print()
    print("Label ranges:")
    for name, score_range in label_ranges():
        print(f"{name}: {score_range}")
