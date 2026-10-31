import re
from .signals import terms

def select(lines, signals, state, budget):
    """Rank candidates within same fixed token allowance. Return (kept, omitted)."""
    if not lines: return [], []
    focus = signals.protected()
    scored = []
    for i, line in enumerate(lines):
        words = terms(line.text)
        relevance = len(words & focus)
        severity = 3 if re.search(r'\b(error|critical|failed|exception|timeout)\b', line.text, re.I) else 0
        rarity = 1 if len(words) <= 18 else 0
        novelty = 0 if __import__('hashlib').sha256(line.text.encode()).hexdigest() in state.seen else 1
        score = severity * 2 + rarity + novelty + 8 * relevance
        scored.append((score, i, line))
    scored.sort(key=lambda x: (-x[0], x[1]))
    kept_ids = set(); used = 0
    for _, i, line in scored:
        cost = max(1, (len(line.text) + 3) // 4)
        if used + cost <= budget:
            kept_ids.add(i); used += cost
    return [line for i,line in enumerate(lines) if i in kept_ids], [line for i,line in enumerate(lines) if i not in kept_ids]
