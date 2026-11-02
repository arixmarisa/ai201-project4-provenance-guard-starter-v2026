
"""
Provenance Guard — Third Detection Signal
Milestone 4 Stretch Feature

Measures repetition in submitted writing by examining
repeated neighboring word pairs (bigrams).

Higher scores indicate more repetitive writing.

This is a heuristic, not proof of AI authorship.
Human writing may intentionally repeat words or phrases.
"""

import sys
from collections import Counter

from stylometry import words


def repetition_signal(text: str) -> float:
    """
    Calculate an AI-likeness score based on repeated bigrams.

    Returns:
        float: A score between 0.0 and 1.0.

    A high score means many neighboring word pairs repeat.
    A low score means relatively few repeated word pairs.
    """

    tokens = words(text)

    # Very short samples do not provide reliable results.
    if len(tokens) < 10:
        return 0.5

    # Create neighboring word pairs.
    bigrams = list(zip(tokens, tokens[1:]))

    # Count each unique pair.
    counts = Counter(bigrams)

    # Count repeated appearances beyond the first.
    repeated = sum(
        count - 1
        for count in counts.values()
        if count > 1
    )

    # Calculate the proportion of repeated word pairs.
    repetition_ratio = repeated / len(bigrams)

    # Normalize the ratio to a score between 0 and 1.
    # A ratio of 0.30 or more results in a score of 1.
    score = repetition_ratio / 0.30

    return round(max(0.0, min(1.0, score)), 4)


if __name__ == "__main__":
    sample = " ".join(sys.argv[1:]) or (
        "The system works well. The system works well. "
        "The system works well every day."
    )

    print("Provenance Guard — Repetition Signal")
    print()
    print(f"Word count: {len(words(sample))}")
    print(f"Repetition score: {repetition_signal(sample)}")
    print()
    print("(Higher scores indicate more repeated word patterns.)")
