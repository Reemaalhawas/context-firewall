"""Layer 1 benchmark: can the firewall handle every data type? Runs locally, no API calls.

Usage: python -m eval.data_types

For each data type (log, json, html, text) a known answer is placed in a large source.
We vary the size, where the answer sits, and how repetitive the noise is, then measure
token saving and whether the answer is kept in the summary or recovered with expand.
"""
import json
import random
from firewall.core import ContextFirewall, approx_tokens

ANSWER = 'ZETA-9041'
NEEDLE = f'payment failed for order code {ANSWER}'
GOAL = 'find the failed payment code'
QUERY = 'failed payment code'
KINDS = ('log', 'json', 'html', 'text')
SIZES = (200, 1000, 5000)
POSITIONS = (0.1, 0.5, 0.9)
NOISES = ('repetitive', 'varied')

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

def make_source(kind, size, position, noise, seed=1):
    rng = random.Random(seed)
    items = [_noise_item(kind, i, noise, rng) for i in range(size)]
    at = int(size * position)
    if kind == 'log':
        items.insert(at, f'2026-10-31T14:32:00Z ERROR {NEEDLE}')
        return '\n'.join(items)
    if kind == 'json':
        items.insert(at, {'id': ANSWER, 'status': 'failed', 'note': NEEDLE})
        return json.dumps({'orders': items})
    if kind == 'html':
        items.insert(at, f'<main><p>Alert: {NEEDLE}.</p></main>')
        return '<html><nav>Home Store Contact</nav>' + ''.join(items) + '<footer>Copyright</footer></html>'
    items.insert(at, f'Alert: {NEEDLE}.')
    return '\n\n'.join(items)

def run_case(kind, size, position, noise, budget=250):
    raw = make_source(kind, size, position, noise)
    fw = ContextFirewall('native', budget=budget); fw.start(GOAL)
    summary = fw.process('read_source', raw)
    in_summary = ANSWER in summary
    recovered = in_summary
    if not in_summary and 'handle=' in summary:
        handle = summary.split('handle=')[1].split(' ')[0]
        recovered = ANSWER in fw.expand(handle, QUERY)
    raw_fw = ContextFirewall('raw'); raw_fw.start(GOAL)
    original, delivered = approx_tokens(raw), approx_tokens(summary)
    return {'kind': kind, 'size': size, 'position': position, 'noise': noise,
            'original_tokens': original, 'delivered_tokens': delivered,
            'saving': 1 - delivered / original, 'in_summary': in_summary, 'recovered': recovered,
            'raw_identity': raw_fw.process('read_source', raw) == raw}

def run_all():
    return [run_case(k, s, p, n) for k in KINDS for n in NOISES for s in SIZES for p in POSITIONS]

def summarize(rows):
    """One row per data type: cases, token saving and how often the answer was found."""
    table = []
    for kind in KINDS:
        sub = [r for r in rows if r['kind'] == kind]
        table.append({'kind': kind, 'cases': len(sub),
                      'original_tokens': sum(r['original_tokens'] for r in sub),
                      'delivered_tokens': sum(r['delivered_tokens'] for r in sub),
                      'avg_saving': sum(r['saving'] for r in sub) / len(sub),
                      'found': sum(r['recovered'] for r in sub),
                      'raw_identity': all(r['raw_identity'] for r in sub)})
    return table

def main():
    rows = run_all()
    print('| Data type | Cases | Tokens before | Tokens after | Avg token saving | Answer found |')
    print('|---|---|---|---|---|---|')
    for t in summarize(rows):
        print(f"| {t['kind']} | {t['cases']} | {t['original_tokens']:,} | {t['delivered_tokens']:,} | "
              f"{t['avg_saving']:.0%} | {t['found']}/{t['cases']} |")
    print(f"\n{len(rows)} cases. Raw passes every source through unchanged: {all(r['raw_identity'] for r in rows)}")

if __name__ == '__main__': main()
