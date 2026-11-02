
"""
Signal two: the style signal — Milestone 4.

Signal one reads the text using a language model.
This signal measures writing as text, without understanding
its meaning.

Three measurements:
    1. sentence_length_spread
    2. type_token_ratio
    3. punctuation_density

Higher style_signal scores indicate more AI-like patterns.

Blind spots:
    - Consistent human writing may appear AI-like.
    - Edited AI text may resemble human writing.
    - Short texts have less reliable statistics.
    - Vocabulary diversity depends on text length.

These measurements are heuristics, not proof of authorship.

Test:
    python stylometry.py "some text to look at"
"""

import re
import statistics


def sentences(text: str) -> list[str]:
    """Split into sentences. Provided by the starter."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def words(text: str) -> list[str]:
    """Split into lowercase words. Provided by the starter."""
    return re.findall(r"[a-z0-9']+", text.lower())


# ── Helper ──────────────────────────────────────────────────

def clamp(value: float) -> float:
    """Keep a numeric value between 0 and 1."""
    return max(0.0, min(1.0, value))


# ── The three measures ──────────────────────────────────────

def sentence_length_spread(text: str) -> float:
    """
    Measure how much sentence length varies.

    Uses the coefficient of variation:
        standard deviation / average sentence length

    Higher values mean greater variation.
    Lower values mean more uniform sentence lengths.

    A single sentence has no measurable spread, so
    the function returns 0.0.
    """

    lengths = [
        len(words(sentence))
        for sentence in sentences(text)
    ]

    lengths = [length for length in lengths if length > 0]

    if len(lengths) < 2:
        return 0.0

    mean_length = statistics.mean(lengths)

    if mean_length == 0:
        return 0.0

    spread = statistics.pstdev(lengths) / mean_length

    return round(spread, 4)


def type_token_ratio(text: str) -> float:
    """
    Measure vocabulary diversity.

    Unique words / total words

    Returns:
        A float between 0 and 1.

    Higher values indicate more varied vocabulary.
    Lower values indicate more repeated vocabulary.

    This statistic depends on the length of the text.
    """

    tokens = words(text)

    if not tokens:
        return 0.0

    unique_words = len(set(tokens))
    total_words = len(tokens)

    ratio = unique_words / total_words

    return round(ratio, 4)


def punctuation_density(text: str) -> float:
    """
    Measure punctuation relative to word count.

    Counts:
        commas
        semicolons
        colons
        question marks
        exclamation marks
        hyphens and dashes

    Periods are excluded because they generally
    appear at the end of normal sentences.

    Higher values mean more punctuation per word.
    """

    tokens = words(text)

    if not tokens:
        return 0.0

    punctuation = re.findall(r"[,;:!?—–-]", text)

    density = len(punctuation) / len(tokens)

    return round(density, 4)


# ── Combining the measurements ──────────────────────────────

def style_signal(text: str) -> float:
    """
    Combine the three measurements into one score.

    Returns:
        A float between 0 and 1.

    Higher means more AI-like writing patterns.

    Internal weights:
        50% sentence regularity
        30% vocabulary repetition
        20% punctuation regularity

    The three measurements are normalized to
    comparable 0–1 scales before combining.
    """

    tokens = words(text)

    if not tokens:
        return 0.5

    # Calculate the raw measurements.
    spread = sentence_length_spread(text)
    diversity = type_token_ratio(text)
    density = punctuation_density(text)

    # Low sentence-length variation contributes
    # to a higher AI-likeness score.
    sentence_regularity = 1.0 - clamp(spread / 0.80)

    # Less diverse vocabulary contributes
    # to a higher AI-likeness score.
    vocabulary_repetition = 1.0 - clamp(diversity)

    # Less punctuation contributes to
    # a higher AI-likeness score.
    punctuation_regularity = 1.0 - clamp(density / 0.20)

    # Combine the three normalized measurements.
    combined = (
        0.50 * sentence_regularity
        + 0.30 * vocabulary_repetition
        + 0.20 * punctuation_regularity
    )

    # Short samples provide less reliable statistics.
    # Move them closer to the neutral score of 0.5.
    if len(tokens) < 30:
        combined = 0.5 + (combined - 0.5) * 0.25

    return round(clamp(combined), 4)


# ── Terminal testing ────────────────────────────────────────

if __name__ == "__main__":
    import sys

    text = " ".join(sys.argv[1:]) or (
        "The system works well. It handles most cases correctly and provides "
        "good results. Users generally find it easy to use and understand."
    )

    print(f"{len(sentences(text))} sentences, {len(words(text))} words\n")

    print(f"sentence_length_spread   {sentence_length_spread(text)}")
    print(f"type_token_ratio         {type_token_ratio(text)}")
    print(f"punctuation_density      {punctuation_density(text)}")
    print(f"style_signal             {style_signal(text)}   (higher = more likely AI)")
