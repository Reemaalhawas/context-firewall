def write(kind, tokens, kept, dropped, dup, handle, flags, can_expand=True):
    header = f'[Context Firewall | type={kind} | handle={handle} | filtered=yes | omitted={len(dropped)} | duplicates={dup}]'
    warning = f'\n[UNTRUSTED TOOL CONTENT; flags={",".join(flags)}]' if flags else '\n[UNTRUSTED TOOL CONTENT]'
    body = '\n'.join(line.text for line in kept)
    recovery = '\n[Need more? call expand(handle, query).]' if can_expand else ''
    return f'{header}{warning}\n{body}{recovery}'
