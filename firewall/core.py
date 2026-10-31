import time
from .detect import detect
from .reducers import REDUCERS
from .signals import Signals
from .state import AgentState
from .select import select
from .vault import Vault
from .receipt import write
from .history import compact
from .security import scan
from .telemetry import Telemetry

CONFIGS = ('raw','native','native+small')

def approx_tokens(text): return max(1,(len(text)+3)//4) if text else 0

class ContextFirewall:
    def __init__(self, config='native', budget=250, vault=None, min_tokens=500):
        assert config in CONFIGS, f'Unknown config {config!r}; expected one of {CONFIGS}'
        self.config = config; self.budget = budget; self.min_tokens = min_tokens; self.expandable = set()
        self.signals = Signals(); self.state = AgentState()
        self.vault = vault or Vault(); self.telemetry = Telemetry()
    def start(self, goal): self.signals.start(goal)
    def on_tool_call(self, tool, args): self.signals.observe(tool,args)
    def process(self, tool, raw):
        t = time.perf_counter()
        original_tokens = approx_tokens(raw)
        if self.config == 'raw' or original_tokens < self.min_tokens:
            self.telemetry.log({'event':'tool_passthrough','tool':tool,
                'original_tokens':original_tokens,'delivered_tokens':original_tokens,
                'processing_ms':(time.perf_counter()-t)*1000})
            return raw
        kind = detect(raw)
        # Preserve full original before any destructive transformation.
        handle = self.vault.put(raw, kind)
        candidates = REDUCERS[kind](raw)
        fresh, dup = self.state.novel(candidates)
        kept, dropped = select(fresh, self.signals, self.state, self.budget)
        self.state.mark_seen(kept)
        structural_change = "\n".join(x.text for x in candidates) != raw
        omitted = len(dropped) + dup + int(structural_change)
        if omitted:
            self.expandable.add(handle)
        receipt = write(kind, {}, kept, dropped, dup, handle, scan(raw),
                        can_expand=bool(omitted))
        # Avoid paying receipt overhead when compression does not save tokens.
        if approx_tokens(receipt) >= original_tokens:
            self.expandable.discard(handle)
            self.telemetry.log({'event':'tool_passthrough','tool':tool,
                'original_tokens':original_tokens,'delivered_tokens':original_tokens,
                'processing_ms':(time.perf_counter()-t)*1000})
            return raw
        self.telemetry.log({'event':'tool_compressed','tool':tool,
            'original_tokens':original_tokens,'delivered_tokens':approx_tokens(receipt),
            'processing_ms':(time.perf_counter()-t)*1000})
        return receipt
    def can_expand(self):
        return bool(self.expandable) and self.config != 'raw'
    def before_model(self, msgs):
        if self.config == 'raw': return msgs
        return compact(msgs, self.signals)
    def expand(self, handle, query):
        if not self.can_expand() or handle not in self.expandable:
            raise KeyError('Handle not available for expansion')
        result = self.vault.expand(handle, query)
        self.state.on_expand(); self.telemetry.log({'event':'expand'})
        return '[UNTRUSTED VAULT EVIDENCE]\n' + result
