"""Layer 1 benchmark: data-type robustness. Runs locally, no API calls.

Usage: python -m eval.data_types

For each data type (log, json, html, text) a known answer is hidden in a large source.
We vary the size, where the answer sits, how repetitive the noise is, and how the answer
is worded: 'clear' uses the words the agent searches for and is marked as an error;
'hidden' uses different words and no error marker. We measure token saving, whether the
answer is kept in the summary, and whether expand recovers it.
"""
import json
import random
from firewall.core import ContextFirewall, approx_tokens

ANSWER = 'ZETA-9041'
NEEDLES = {'clear': (f'payment failed for order code {ANSWER}', 'ERROR'),
           'hidden': (f'order {ANSWER} was declined by the bank', 'INFO')}
GOAL = 'find the failed payment code'
QUERY = 'failed payment code'
KINDS = ('log', 'json', 'html', 'text')
SIZES = (200, 1000, 5000)
POSITIONS = (0.1, 0.5, 0.9)
NOISES = ('repetitive', 'varied')
WORDINGS = tuple(NEEDLES)

SERVICES = ['auth', 'billing', 'search', 'cart', 'gateway', 'catalog', 'profile', 'notify']
ACTIONS = ['request completed', 'cache refreshed', 'session renewed', 'job scheduled', 'record synced', 'health check ok']
WORDS = ['shipping', 'warranty', 'returns', 'delivery', 'support', 'account', 'pricing', 'catalog', 'update', 'policy']

def _noise_item(kind, i, noise, rng):
    if noise == 'repetitive':
        return {'log': f'2026-10-31T14:{i%60:02d}:00Z INFO request completed id={i} latency=20ms',
                'json': {'id': f'A-{i:05d}', 'status': 'paid', 'region': 'eu'},
                'html': f'<p>Catalog entry {i}: standard terms and delivery information.</p>',
                'text': f'Status note {i}: all systems are running normally.'}[kind]
    svc, act = rng.choice(SERVICES), rng.choice(ACTIONS)
    words = ' '.join(rng.sample(WORDS, 4))
    return {'log': f'2026-10-31T{rng.randrange(24):02d}:{rng.randrange(60):02d}:{rng.randrange(60):02d}Z '
                   f'{rng.choice(["INFO", "DEBUG"])} {svc} {act} user={rng.randrange(10**6)} took={rng.randrange(5, 900)}ms',
            'json': {'id': f'A-{i:05d}', 'status': rng.choice(['paid', 'refunded', 'pending']),
                     'service': svc, 'amount': rng.randrange(5, 999), 'note': words},
            'html': f'<p>{svc.title()} {words} item {rng.randrange(10**5)}.</p>',
            'text': f'{svc.title()} team note {rng.randrange(10**5)}: {act}, see {words}.'}[kind]

def make_source(kind, size, position, noise, wording='clear', seed=1):
    rng = random.Random(seed)
    items = [_noise_item(kind, i, noise, rng) for i in range(size)]
    at = int(size * position)
    needle, level = NEEDLES[wording]
    if kind == 'log':
        items.insert(at, f'2026-10-31T14:32:00Z {level} {needle}')
        return '\n'.join(items)
    if kind == 'json':
        items.insert(at, {'id': ANSWER, 'status': 'failed' if wording == 'clear' else 'closed', 'note': needle})
        return json.dumps({'orders': items})
    if kind == 'html':
        items.insert(at, f'<main><p>Alert: {needle}.</p></main>')
        return '<html><nav>Home Store Contact</nav>' + ''.join(items) + '<footer>Copyright</footer></html>'
    items.insert(at, f'Alert: {needle}.')
    return '\n\n'.join(items)

def run_case(kind, size, position, noise, wording='clear', budget=250):
    raw = make_source(kind, size, position, noise, wording)
    fw = ContextFirewall('native', budget=budget); fw.start(GOAL)
    summary = fw.process('read_source', raw)
    in_summary = ANSWER in summary
    recovered = in_summary
    if not in_summary and 'handle=' in summary:
        handle = summary.split('handle=')[1].split(' ')[0]
        recovered = ANSWER in fw.expand(handle, QUERY)
    raw_fw = ContextFirewall('raw'); raw_fw.start(GOAL)
    original, delivered = approx_tokens(raw), approx_tokens(summary)
    return {'kind': kind, 'size': size, 'position': position, 'noise': noise, 'wording': wording,
            'original_tokens': original, 'delivered_tokens': delivered,
            'saving': 1 - delivered / original, 'in_summary': in_summary, 'recovered': recovered,
            'raw_identity': raw_fw.process('read_source', raw) == raw}

def run_all():
    return [run_case(k, s, p, n, w) for k in KINDS for w in WORDINGS for n in NOISES for s in SIZES for p in POSITIONS]

def summarize(rows):
    """One row per data type: token saving, and how often the answer was found per wording."""
    table = []
    for kind in KINDS:
        sub = [r for r in rows if r['kind'] == kind]
        row = {'kind': kind, 'avg_saving': sum(r['saving'] for r in sub) / len(sub),
               'raw_identity': all(r['raw_identity'] for r in sub)}
        for w in WORDINGS:
            part = [r for r in sub if r['wording'] == w]
            row[w] = (sum(r['recovered'] for r in part), len(part))
        table.append(row)
    return table

def main():
    rows = run_all()
    print('| Data type | Avg token saving | Clear answer found | Hidden answer found |')
    print('|---|---|---|---|')
    for t in summarize(rows):
        print(f"| {t['kind']} | {t['avg_saving']:.0%} | {t['clear'][0]}/{t['clear'][1]} | {t['hidden'][0]}/{t['hidden'][1]} |")
    print(f"\n{len(rows)} cases. Raw passes every source through unchanged: {all(r['raw_identity'] for r in rows)}")

if __name__ == '__main__': main()
