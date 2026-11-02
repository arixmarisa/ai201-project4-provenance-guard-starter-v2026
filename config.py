
"""
Settings for Provenance Guard.

Everything you're likely to change lives here, at the top, on purpose.

Milestone 4:
    - Three weighted detection signals
    - Disagreement handling

Milestone 5:
    - Classification thresholds and final labels

Unit 8:
    - Rate limiting and adversarial evaluation
"""

import os
from pathlib import Path


ROOT = Path(__file__).parent


# ─── The service ─────────────────────────────────────────────────────────────

# 127.0.0.1 is loopback, so only your own computer can access the service.
# The HOST environment variable can override this for deployment.
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))

# Debug mode should only be available on the local machine.
# Never expose the Flask interactive debugger publicly.
DEBUG = (
    os.getenv("AI201_DEBUG", "1") == "1"
    and HOST in ("127.0.0.1", "localhost")
)


# ─── The local model ─────────────────────────────────────────────────────────

# The first signal runs a local GPT-2 language model.
# No API key or hosted service is required.
#
# The model measures the predictability of text.
# Predictable writing may receive a higher AI-likeness score,
# but this does not prove AI authorship.

DETECTOR_MODEL = os.getenv("AI201_DETECTOR_MODEL", "gpt2")

# Limit the number of tokens processed by the detector.
# Longer passages provide more context but require more processing.
DETECTOR_MAX_TOKENS = 400


# ─── Scoring (Milestone 4) ───────────────────────────────────────────────────

# Provenance Guard combines three independent signals.
#
# Signal 1: Language model
#   Analyzes text predictability using GPT-2.
#
# Signal 2: Stylometry
#   Analyzes sentence-length variation, vocabulary diversity,
#   and punctuation density.
#
# Signal 3: Repetition (stretch feature)
#   Analyzes repeated neighboring word pairs.
#
# Higher scores indicate more AI-like writing patterns.
# All scores are expected to fall between 0.0 and 1.0.
#
# The weights were selected to prioritize the local model
# while incorporating additional writing characteristics.
#
# Combined score:
#
#   (0.50 * model_score)
# + (0.30 * style_score)
# + (0.20 * repetition_score)

WEIGHT_MODEL_SIGNAL = 0.50
WEIGHT_STYLE_SIGNAL = 0.30
WEIGHT_REPETITION_SIGNAL = 0.20


# ─── Disagreement handling (Milestone 4) ─────────────────────────────────────

# When the signals disagree substantially, the system should
# communicate uncertainty instead of making a strong accusation.
#
# Example:
#   model_score      = 0.90
#   style_score      = 0.20
#   repetition_score = 0.10
#
#   Weighted score = 0.53
#
# Since the largest and smallest signal differ by 0.80,
# the disagreement safeguard applies:
#
#   adjusted_score = 0.50 + (0.53 - 0.50) * 0.50
#                  = 0.515
#
# This moves the final result closer to uncertainty.

DISAGREEMENT_THRESHOLD = 0.45
DISAGREEMENT_SHRINK = 0.50


# ─── Thresholds (Milestone 5) ────────────────────────────────────────────────

# The final score will determine one of three classifications.
#
# Scores:
#
#   0.00 <= score <= 0.30  -> High-confidence human
#   0.30 < score < 0.80    -> Unsure
#   0.80 <= score <= 1.00  -> High-confidence AI
#
# These thresholds are deliberately conservative.
#
# A false positive occurs when human writing is classified
# as AI-generated. Such an accusation can damage a writer's
# credibility, so uncertainty is preferable when signals
# do not strongly agree.

HUMAN_THRESHOLD = 0.30
AI_THRESHOLD = 0.80


# ─── Rate limiting (UNIT 8) ──────────────────────────────────────────────────

# Rate limiting remains disabled during Unit 7.
#
# In Unit 8, we will enable it to reduce repeated automated
# requests intended to probe or manipulate classification scores.
#
# Enable with:
#   AI201_RATE_LIMITS=1 python app.py

RATE_LIMITING_ENABLED = os.getenv("AI201_RATE_LIMITS", "0") == "1"

# Maximum number of requests permitted per minute and per day.
# These settings are reserved for Unit 8.
RATE_LIMIT_PER_MINUTE = 10
RATE_LIMIT_PER_DAY = 200

# In-memory storage is suitable for this local coursework project.
# It is not appropriate for a distributed production service because
# counters are lost when the application restarts.
RATE_LIMIT_STORAGE = "memory://"


# ─── Paths ───────────────────────────────────────────────────────────────────

# Directory containing the project.
ROOT = Path(__file__).parent

# Structured audit records are stored here.
LOG_DIR = ROOT / "logs"
AUDIT_LOG = LOG_DIR / "audit.jsonl"

# Evaluation output will be stored here during Unit 8.
RESULTS_DIR = ROOT / "results"
