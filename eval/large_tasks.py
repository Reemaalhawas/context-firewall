"""Deterministic, development-only stress fixtures. Never modifies held-out tasks."""
import json

SIZES = (500, 2000, 5000, 10000)

def make_large_tasks():
    tasks = []
    for target in SIZES:
        # Size denotes approximate raw source tokens, not total model tokens.
        count = max(10, target * 4 // 58)
        logs = [f'INFO checkout succeeded id={i} latency={20 + i % 7}ms' for i in range(count)]
        logs.insert(len(logs)//2, 'ERROR payment database timeout code=PAY-72')
        logs.append('CRITICAL connection refused at db-retired.internal')
        tasks.append({'id':f'dev-large-payment-{target}', 'split':'dev',
          'prompt':'Investigate checkout failure. Read logs AND config. Return root_cause and faulty_host exactly.',
          'sources':{'logs':'\n'.join(logs),
             'config':json.dumps({'service':{'database':{'host':'db-retired.internal','port':5432},
             'retries':3}, 'noise':[{'key':f'config_{i}','value':f'unchanged_{i}'} for i in range(max(5,count//4))]})},
          'expected':{'root_cause':'database connection timeout','faulty_host':'db-retired.internal'}})
        noise = [f'<p>Routine status update {i}: all regions operational.</p>' for i in range(count)]
        noise.insert(len(noise)//2, '<p>Incident code INC-4821 impacted billing API.</p>')
        html = '<html><nav>Home Contact Careers</nav><main>' + ''.join(noise) + '</main><footer>Privacy</footer></html>'
        tasks.append({'id':f'dev-large-web-{target}', 'split':'dev',
          'prompt':'Read website and support tickets. Return incident_code and affected_service exactly.',
          'sources':{'website':html, 'tickets':'INFO ticket processed id=1\nWARN billing API unavailable'},
          'expected':{'incident_code':'INC-4821','affected_service':'billing API'}})
        metrics = {'company':{'name':'Nova','financials':{'arr':1500000,'nrr':118},
          'activity':[{'event':f'event_{i}', 'status':'completed','value':i} for i in range(count)]}}
        tasks.append({'id':f'dev-large-financial-{target}', 'split':'dev',
          'prompt':'Evaluate Nova metrics. Read financials and notes. Return arr and runway_months exactly.',
          'sources':{'financials':json.dumps(metrics), 'notes':'Board memo: current cash runway is 8 months.'},
          'expected':{'arr':1500000,'runway_months':8}})
    return tasks
