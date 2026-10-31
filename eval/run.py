"""Usage: python -m eval.run --split dev --suite challenge --config all --models gpt-4o-mini,gpt-4o --repeats 1"""
import argparse
import json
import os
import statistics
from pathlib import Path
from agent.agent import run_agent, resolve_model
from firewall.core import CONFIGS
from firewall.detect import detect
from .large_tasks import make_large_tasks
from .challenge_tasks import make_challenge_tasks

def check_answer(answer, expected):
    if not isinstance(answer,dict): return False
    return all(str(answer.get(k,'')).strip().lower()==str(v).strip().lower() for k,v in expected.items())

def percentile(values,p):
    if not values: return None
    vals = sorted(values); pos = (len(vals)-1)*p; lo=int(pos); hi=min(lo+1,len(vals)-1)
    return vals[lo]+(vals[hi]-vals[lo])*(pos-lo)

def task_data_type(task):
    """A task's data type is the detected format of its largest source."""
    return detect(max(task['sources'].values(), key=len))

def agent_pairs(configs, models):
    """Unique (config, model) agents; native+small resolves to CF_SMALL_MODEL once."""
    pairs = []
    for model in models:
        for config in configs:
            pair = (config, resolve_model(config, model))
            if pair not in pairs: pairs.append(pair)
    return pairs

def _stats(subset, price_in, price_out):
    successes = sum(r['success'] for r in subset)
    total_cost = sum((r['prompt_tokens']*price_in+r['completion_tokens']*price_out)/1e6 for r in subset)
    return {
        'runs':len(subset),'success_rate':successes/len(subset),
        'total_tokens':sum(r['total_tokens'] for r in subset),
        'avg_tokens':statistics.mean(r['total_tokens'] for r in subset),
        'avg_steps':statistics.mean(r['steps'] for r in subset),
        'expand_calls':sum(r['firewall']['expands'] for r in subset),
        'errors':sum('error' in r for r in subset),
        'p95_latency_ms':round(percentile([r['latency_ms'] for r in subset],.95),2),
        'total_cost_usd':round(total_cost,6),
        'cost_per_success_usd':round(total_cost/successes,6) if successes else None
    }

def aggregate(rows, price_in=0, price_out=0):
    """Two report levels: overall per agent, and per data type per agent."""
    agents = sorted({r['agent'] for r in rows})
    by_agent = {a:_stats([r for r in rows if r['agent']==a],price_in,price_out) for a in agents}
    by_data_type = {}
    for kind in sorted({r['data_type'] for r in rows}):
        subset = [r for r in rows if r['data_type']==kind]
        by_data_type[kind] = {a:_stats([r for r in subset if r['agent']==a],price_in,price_out)
                              for a in agents if any(r['agent']==a for r in subset)}
    return {'by_agent':by_agent,'by_data_type':by_data_type}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split',choices=['dev','heldout'],default='dev')
    ap.add_argument('--suite',choices=['standard','large','challenge'],default='standard',help='large: generated development stress fixtures')
    ap.add_argument('--config',choices=list(CONFIGS)+['all'],default='all')
    ap.add_argument('--models',default=None,help='Comma-separated models to benchmark as separate agents (default: CF_MODEL)')
    ap.add_argument('--repeats',type=int,default=1)
    ap.add_argument('--limit',type=int,default=None,help='Run only the first N tasks (development smoke tests)')
    ap.add_argument('--budget',type=int,default=250)
    ap.add_argument('--input-price',type=float,default=0,help='USD per 1M input tokens')
    ap.add_argument('--output-price',type=float,default=0,help='USD per 1M output tokens')
    ap.add_argument('--out',default='results')
    ap.add_argument('--confirm-heldout',action='store_true',help='Explicitly authorize final held-out evaluation')
    args = ap.parse_args()
    if args.split=='heldout' and args.suite=='large': ap.error('Large suite is development-only.')
    if args.split=='heldout' and not args.confirm_heldout:
        ap.error('Held-out split is reserved. Pass --confirm-heldout for the final run.')
    if args.repeats<1: ap.error('--repeats must be >=1')
    if not os.getenv('OPENAI_API_KEY'): ap.error('Set OPENAI_API_KEY before real-agent evaluation.')
    try: import openai  # noqa: F401
    except ImportError: ap.error('The openai package is missing. Run: uv sync --extra agent --extra test')
    tasks = (make_challenge_tasks(args.split) if args.suite=='challenge' else make_large_tasks() if args.suite=='large' else
             [t for t in json.loads((Path(__file__).parent/'tasks.json').read_text()) if t['split']==args.split])
    if args.limit is not None:
        if args.limit < 1: ap.error('--limit must be >= 1')
        tasks = tasks[:args.limit]
    configs = list(CONFIGS) if args.config=='all' else [args.config]
    models = [m.strip() for m in args.models.split(',') if m.strip()] if args.models else [None]
    agents = agent_pairs(configs, models)
    out = Path(args.out); out.mkdir(exist_ok=True,parents=True)
    prefix = f'{args.split}_{args.suite}'
    if args.split=='heldout' and (out/'heldout.lock').exists():
        ap.error('Held-out run already recorded in this results directory. Do not tune/re-run held-out.')
    if args.split=='heldout': (out/'heldout.lock').write_text('Held-out evaluation started. Do not rerun.\n')
    rows=[]
    (out/f'{prefix}_runs.jsonl').write_text('')
    for task in tasks:
        data_type = task_data_type(task)
        for config, model in agents:
            agent = f'{config}@{model}'
            for repeat in range(args.repeats):
                try:
                    result = run_agent(task,config,model,args.budget)
                    result.update(success=check_answer(result['answer'],task['expected']) and not any(str(x).lower() in json.dumps(result['answer'],ensure_ascii=False).lower() for x in task.get('forbidden',[])))
                except Exception as exc:
                    result = {'success':False,'error':str(exc),'model':model,'prompt_tokens':0,'completion_tokens':0,'total_tokens':0,'steps':0,'latency_ms':0,'firewall':{'expands':0}}
                result.update(task_id=task['id'],config=config,agent=agent,data_type=data_type,repeat=repeat)
                rows.append(result)
                with (out/f'{prefix}_runs.jsonl').open('a') as f: f.write(json.dumps(result)+'\n')
                print(task['id'],data_type,agent,repeat,'PASS' if result['success'] else 'FAIL')
    summary = aggregate(rows,args.input_price,args.output_price)
    (out/f'{prefix}_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
