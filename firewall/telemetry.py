import time
class Telemetry:
    def __init__(self): self.events = []
    def log(self, event): self.events.append({'at':time.perf_counter(), **event})
    def summary(self):
        comp = [e for e in self.events if e.get('event') == 'tool_compressed']
        return {'tool_calls':len(comp), 'original_tool_tokens':sum(e['original_tokens'] for e in comp), 'delivered_tool_tokens':sum(e['delivered_tokens'] for e in comp), 'firewall_ms':sum(e['processing_ms'] for e in comp), 'expands':sum(e.get('event')=='expand' for e in self.events)}
