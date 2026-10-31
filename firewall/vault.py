import json
import re
import sqlite3
import uuid

def _units(raw, kind):
    """Split raw evidence into searchable units: JSON records, HTML blocks, or lines."""
    if kind == 'json':
        try: data = json.loads(raw)
        except ValueError: return raw.splitlines()
        units = []
        def walk(x):
            if isinstance(x, list):
                for item in x: walk(item)
            elif isinstance(x, dict):
                scalars = {k:v for k,v in x.items() if not isinstance(v,(dict,list))}
                if scalars: units.append(json.dumps(scalars, ensure_ascii=False))
                for v in x.values():
                    if isinstance(v,(dict,list)): walk(v)
            else: units.append(json.dumps(x, ensure_ascii=False))
        walk(data)
        return units
    if kind == 'html':
        return [u for u in re.split(r'(?=<(?:p|aside|main|article|section|div|li|tr|h[1-6]|nav|footer)\b)', raw, flags=re.I) if u.strip()]
    return raw.splitlines()
class Vault:
    def __init__(self, path=':memory:', run_id=None):
        self.db = sqlite3.connect(path)
        self.run_id = run_id or uuid.uuid4().hex
        self.db.execute('CREATE TABLE IF NOT EXISTS vault (handle TEXT PRIMARY KEY, run_id TEXT, kind TEXT, raw TEXT)')
    def put(self, raw, kind):
        handle = 'v_' + uuid.uuid4().hex[:12]
        self.db.execute('INSERT INTO vault VALUES (?,?,?,?)',(handle,self.run_id,kind,raw)); self.db.commit()
        return handle
    def expand(self, handle, query='', limit=1800):
        row = self.db.execute('SELECT raw, kind FROM vault WHERE handle=? AND run_id=?',(handle,self.run_id)).fetchone()
        if not row: raise KeyError('Unknown or unauthorized handle')
        raw, kind = row
        if not query: return raw[:limit]
        keywords = [x for x in query.lower().split() if len(x)>2]
        lines = _units(raw, kind)
        ranked = sorted(enumerate(lines), key=lambda pair: (-sum(w in pair[1].lower() for w in keywords), pair[0]))
        return '\n'.join(line for _,line in ranked if any(w in line.lower() for w in keywords))[:limit] or raw[:limit]
