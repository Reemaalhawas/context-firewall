"""Two test levels: every data type through the firewall, and agent (config x model) benchmarking."""
import json
import pytest
from agent.agent import resolve_model
from eval.challenge_tasks import make_challenge_tasks
from eval.run import agent_pairs, task_data_type
from firewall.core import ContextFirewall
from firewall.detect import detect

ANSWER = 'ZETA-9041'
SOURCES = {
    'log': '\n'.join(f'INFO request completed id={i} latency=20ms' for i in range(1500)) + f'\nCRITICAL disk failure code={ANSWER}',
    'json': json.dumps({'orders':[{'id':f'A-{i:04d}','status':'paid'} for i in range(800)] + [{'id':ANSWER,'status':'failed'}]}),
    'html': '<html><nav>Home Store</nav>' + '<p>Catalog entry: standard terms.</p>'*1500 + f'<main><p>Failed code {ANSWER}</p></main></html>',
    'text': '\n\n'.join(f'Routine status note {i}: all systems nominal today.' for i in range(800)) + f'\n\nFailed code recorded: {ANSWER}.',
}

@pytest.mark.parametrize('kind', sorted(SOURCES))
def test_data_type_compresses_and_recovers(kind):
    raw = SOURCES[kind]
    assert detect(raw) == kind
    fw = ContextFirewall('native', budget=250); fw.start('find the failed code')
    receipt = fw.process('read_source', raw)
    summary = fw.telemetry.summary()
    assert summary['delivered_tool_tokens'] < summary['original_tool_tokens'], kind
    if ANSWER not in receipt:
        handle = receipt.split('handle=')[1].split(' ')[0]
        assert ANSWER in fw.expand(handle, 'failed code'), kind

@pytest.mark.parametrize('kind', sorted(SOURCES))
def test_data_type_raw_is_identity(kind):
    fw = ContextFirewall('raw'); fw.start('find the failed code')
    assert fw.process('read_source', SOURCES[kind]) == SOURCES[kind]

def test_challenge_suite_covers_multiple_data_types():
    kinds = {task_data_type(t) for t in make_challenge_tasks('dev')}
    assert {'log','json','html'} <= kinds

def test_agent_pairs_cover_each_model(monkeypatch):
    monkeypatch.setenv('CF_SMALL_MODEL', 'small-model')
    pairs = agent_pairs(['raw','native','native+small'], ['model-a','model-b'])
    assert pairs == [('raw','model-a'),('native','model-a'),('native+small','small-model'),
                     ('raw','model-b'),('native','model-b')]

def test_resolve_model_defaults(monkeypatch):
    monkeypatch.setenv('CF_MODEL', 'default-model'); monkeypatch.delenv('CF_SMALL_MODEL', raising=False)
    assert resolve_model('native') == 'default-model'
    assert resolve_model('native+small') == 'default-model'
    assert resolve_model('raw', 'explicit') == 'explicit'

def test_data_type_benchmark_clear_answers_always_found():
    from eval.data_types import KINDS, NOISES, POSITIONS, run_case
    for kind in KINDS:
        for noise in NOISES:
            for position in POSITIONS:
                r = run_case(kind, 1000, position, noise, 'clear')
                assert r['recovered'] and r['saving'] > 0.5 and r['raw_identity'], r
