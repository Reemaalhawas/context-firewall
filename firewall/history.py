def compact(msgs, signals, keep_recent=6):
    """Conservative compaction: only old tool messages, keep protocol roles intact.
    The caller should retain full originals separately. For tool-call APIs, compact
    message content in place rather than removing tool response messages.
    """
    result = [dict(m) for m in msgs]
    for i, msg in enumerate(result[:-keep_recent] if keep_recent else result):
        if msg.get('role') == 'tool' and isinstance(msg.get('content'), str) and len(msg['content']) > 240:
            lines = msg['content'].splitlines()
            matching = [line for line in lines if any(term in line.lower() for term in signals.protected())]
            excerpt = '\n'.join(matching[:3])[:160]
            handle = next((part.split('handle=')[1].split(' ')[0].split('|')[0].strip() for part in lines if 'handle=' in part), 'unknown')
            msg['content'] = f'[Earlier filtered tool result; handle={handle}; excerpt={excerpt}]'
    return result
