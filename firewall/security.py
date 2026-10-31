import re
PATTERNS = [r'ignore (?:all )?(?:previous|prior) instructions', r'reveal (?:your|the) system prompt', r'تجاهل التعليمات']
def scan(text, deep=False):
    return ['suspected_prompt_injection'] if any(re.search(p, text, re.I) for p in PATTERNS) else []
def strip_injections(text):
    # Optional only: filtering can remove legitimate evidence. Do not rely on this for safety.
    return '\n'.join(line for line in text.splitlines() if not scan(line))
