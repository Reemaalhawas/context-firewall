import hashlib
class AgentState:
    def __init__(self): self.seen = set(); self.expands = 0
    def novel(self, lines):
        fresh = []; dup = 0
        for line in lines:
            digest = hashlib.sha256(line.text.encode()).hexdigest()
            if digest in self.seen: dup += 1
            else: fresh.append(line)
        return fresh, dup
    def mark_seen(self, lines):
        for line in lines: self.seen.add(hashlib.sha256(line.text.encode()).hexdigest())
    def on_expand(self): self.expands += 1
