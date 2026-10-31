import json
import re
from eval.challenge_tasks import make_challenge_tasks
from eval.run import check_answer
from firewall.core import ContextFirewall


def test_challenge_split_and_categories():
    dev = make_challenge_tasks('dev')
    heldout = make_challenge_tasks('heldout')
    assert len(dev) == 12 and len(heldout) == 6
    assert {t['category'] for t in dev} == {'A','B','C'}
    assert {t['category'] for t in heldout} == {'A','B','C'}
    assert not {t['id'] for t in dev} & {t['id'] for t in heldout}
    assert make_challenge_tasks('dev') == dev


def test_answers_planted_and_judged():
    for task in make_challenge_tasks('dev') + make_challenge_tasks('heldout'):
        joined = '\n'.join(task['sources'].values())
        for value in task['expected'].values():
            assert str(value) in joined, task['id']
        assert check_answer(task['expected'], task['expected'])
        assert not check_answer({}, task['expected'])


def test_realistically_large_sources():
    for task in make_challenge_tasks('dev'):
        assert max(map(len,task['sources'].values())) > 14000, task['id']
    assert len(make_challenge_tasks('heldout')[2]['sources']['logs'].splitlines()) >= 50000


def test_native_receives_dynamic_focus_from_tool_argument():
    fw = ContextFirewall('native')
    fw.start('Identify the memory limit of the affected node')
    fw.on_tool_call('read_source',{'name':'workers','focus':'worker-3'})
    assert 'worker-3' in fw.signals.protected()


def test_small_output_still_passes_through():
    fw = ContextFirewall('native')
    fw.start('investigate')
    assert fw.process('read_source','Small result') == 'Small result'
    assert not fw.can_expand()


def test_json_array_keeps_record_associations():
    from firewall.reducers import reduce_json
    rows = reduce_json('{"workers":[{"id":"worker-3","memory_limit":"1536MiB"}]}')
    assert any('worker-3' in x.text and '1536MiB' in x.text for x in rows)


def test_native_focus_prioritizes_specific_record():
    from firewall.reducers import reduce_json
    from firewall.select import select
    from firewall.signals import Signals
    from firewall.state import AgentState
    rows = reduce_json('{"workers":[{"id":"worker-1","memory_limit":"512MiB"},{"id":"worker-3","memory_limit":"1536MiB"}]}')
    s = Signals(); s.start('Find the memory limit of the affected worker')
    s.observe('read_source', {'name':'workers','focus':'worker-3'})
    kept,_ = select(rows,s,AgentState(),35)
    assert any('worker-3' in x.text and '1536MiB' in x.text for x in kept)
