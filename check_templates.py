import os
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
env = Environment(loader=FileSystemLoader(root))
bad = 0
total = 0
for dp, _, files in os.walk(root):
    for f in files:
        if f.endswith('.html'):
            total += 1
            rel = os.path.relpath(os.path.join(dp, f), root)
            try:
                env.get_template(rel)
            except TemplateSyntaxError as e:
                bad += 1
                print(f'SYNTAX ERROR {rel}:{e.lineno}: {e.message}')
print(f'{total} templates checked, {bad} with errors')
