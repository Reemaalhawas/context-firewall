import re
STOP = {'the','and','for','from','with','that','this','find','what','where','which','show','about','into','using','error','please','need'}
def terms(s):
    return {x for x in re.findall(r'[a-zA-Z_][a-zA-Z_0-9]*(?:-[a-zA-Z_0-9]+)*', str(s).lower()) if len(x)>=3 and x not in STOP}
class Signals:
    def __init__(self): self.goal = set(); self.focus = set()
    def start(self, goal): self.goal = terms(goal); self.focus = set()
    def observe(self, tool, args):
        # Only public tool name/arguments; never private chain of thought.
        self.focus = terms(tool + ' ' + ' '.join(str(v) for v in args.values()))
    def protected(self): return self.goal | self.focus
