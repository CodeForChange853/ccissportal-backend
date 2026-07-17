import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ── Command intent patterns ───────────────────────────────────────────────────
# Tuple: (compiled regex, action_type, has_named_target)
_PATTERNS = [
    (re.compile(r"^(?:suspend|ban|lock|deactivate)\s+(.+)$"),         "SUSPEND_USER",    True),
    (re.compile(r"^(?:activate|unban|unlock|restore|enable)\s+(.+)$"),"ACTIVATE_USER",   True),
    (re.compile(r"^(?:maintenance|maintenance\s+mode)\s+(?:on|enable|start)$"),  "MAINTENANCE_ON",  False),
    (re.compile(r"^(?:turn\s+on|enable|start)\s+maintenance(?:\s+mode)?$"),      "MAINTENANCE_ON",  False),
    (re.compile(r"^(?:maintenance|maintenance\s+mode)\s+(?:off|disable|stop)$"), "MAINTENANCE_OFF", False),
    (re.compile(r"^(?:turn\s+off|disable|stop)\s+maintenance(?:\s+mode)?$"),     "MAINTENANCE_OFF", False),
]

_STRIP_VERBS = {"manage", "view", "edit", "find", "search", "update", "show"}


def parse_command_intent(query: str) -> tuple[str | None, str | None]:
    """
    Detects action commands in the query.
    Returns (action_type, target_name) or (None, None).
    """
    q = query.lower().strip()
    for pattern, action_type, has_target in _PATTERNS:
        m = pattern.match(q)
        if m:
            target = m.group(1).strip() if has_target else None
            return action_type, target
    return None, None


def strip_verb_prefix(query: str) -> str:
    """Removes leading action verbs from plain search queries."""
    parts = query.lower().strip().split(" ", 1)
    if len(parts) == 2 and parts[0] in _STRIP_VERBS:
        return parts[1].strip()
    return query.strip()


def score_by_tfidf(query: str, texts: list[str]) -> list[float]:
    """
    Returns cosine similarity scores (0–1) for each text against the query.
    Uses character n-grams (2–4) — robust for short strings and partial names.
    Falls back to uniform 1.0 if the vectorizer cannot fit (e.g. empty corpus).
    """
    if not texts:
        return []
    try:
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
        matrix = vectorizer.fit_transform([query] + texts)
        scores = cosine_similarity(matrix[0:1], matrix[1:]).flatten()
        return [round(float(s), 4) for s in scores]
    except Exception:
        return [1.0] * len(texts)
