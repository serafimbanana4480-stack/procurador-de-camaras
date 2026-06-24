"""Check all imports from models across the project."""
import ast
import os
import sys

base = os.path.dirname(os.path.abspath(__file__))
proj = os.path.join(base, "procurador")

issues = []
for root, dirs, files in os.walk(proj):
    for f in files:
        if not f.endswith('.py') or f.startswith('__pycache__'):
            continue
        path = os.path.join(root, f)
        try:
            with open(path, 'r', encoding='utf-8') as fh:
                tree = ast.parse(fh.read())
        except Exception as e:
            issues.append((path, f"PARSE ERROR: {e}"))
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and 'models' in node.module:
                for n in node.names:
                    if n.name != '*':
                        issues.append((path, f"imports {n.name}"))

for path, msg in issues:
    print(f"{path}: {msg}")
