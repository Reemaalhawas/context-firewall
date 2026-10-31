import json
import re

def detect(text: str) -> str:
    s = text.strip()
    if not s:
        return 'text'
    try:
        if isinstance(json.loads(s), (dict, list)):
            return 'json'
    except (ValueError, TypeError):
        pass
    if re.search(r'<(?:html|body|main|article|div|p|nav|script)\b', s, re.I):
        return 'html'
    lines = [x for x in s.splitlines() if x.strip()]
    if lines and sum(bool(re.search(r'\b(?:DEBUG|INFO|WARN|WARNING|ERROR|CRITICAL)\b', x)) for x in lines) / len(lines) >= .5:
        return 'log'
    return 'text'
