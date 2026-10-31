"""Lossy structural candidate generation. Full original remains in Vault."""
import json
import re
from collections import OrderedDict
from dataclasses import dataclass
from html.parser import HTMLParser

@dataclass
class Line:
    text: str
    source: str = ''

class _HTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','nav','footer'):
            self.skip += 1
    def handle_endtag(self, tag):
        if tag in ('script','style','nav','footer') and self.skip:
            self.skip -= 1
    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())

def reduce_html(text):
    p = _HTML(); p.feed(text)
    return [Line(x, 'html') for x in p.parts]

def reduce_json(text):
    obj = json.loads(text); out = []
    def walk(value, path='root'):
        if isinstance(value, dict):
            if not value: out.append(Line(f'{path}={{}}', path))
            for k, v in value.items(): walk(v, f'{path}.{k}')
        elif isinstance(value, list):
            if not value: out.append(Line(f'{path}=[]', path))
            for i, v in enumerate(value):
                if isinstance(v, dict):
                    # Keep related record fields together so selecting an ID also retains its value.
                    out.append(Line(f'{path}[{i}]={json.dumps(v, ensure_ascii=False, separators=(",",":"))}', f'{path}[{i}]'))
                else: walk(v, f'{path}[{i}]')
        else: out.append(Line(f'{path}={json.dumps(value, ensure_ascii=False)}', path))
    walk(obj)
    return out

def reduce_log(text):
    groups = OrderedDict()
    for index, raw in enumerate(text.splitlines()):
        if not raw.strip(): continue
        # Keep errors and unusual records verbatim: IDs/numbers may be diagnostic.
        if re.search(r'\b(ERROR|CRITICAL|WARN|WARNING)\b', raw):
            groups[f'unique:{index}'] = [raw]
            continue
        template = re.sub(r'\bid=\d+\b', 'id=<ID>', raw)
        template = re.sub(r'\blatency=\d+ms\b', 'latency=<NUM>ms', template)
        groups.setdefault(template, []).append(raw)
    result = []
    for key, rows in groups.items():
        if key.startswith('unique:') or len(rows) == 1:
            result.append(Line(rows[0], 'log'))
        else:
            # Preserve range of latency values when grouping.
            nums = [int(x) for row in rows for x in re.findall(r'latency=(\d+)ms', row)]
            suffix = f' latency_range={min(nums)}-{max(nums)}ms' if nums else ''
            result.append(Line(f'{key} [count={len(rows)}]{suffix}', 'log'))
    return result

def reduce_text(text):
    chunks = re.split(r'\n\s*\n', text.strip())
    if len(chunks) == 1:
        chunks = text.splitlines()
    seen = set(); out = []
    for chunk in chunks:
        chunk = chunk.strip()
        if chunk and chunk not in seen:
            seen.add(chunk); out.append(Line(chunk, 'text'))
    return out

REDUCERS = {'log':reduce_log, 'json':reduce_json, 'html':reduce_html, 'text':reduce_text}
