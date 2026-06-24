"""Check imports between __main__ and other modules."""
import ast
import os

base = os.path.dirname(os.path.abspath(__file__))
main_path = os.path.join(base, "procurador", "__main__.py")

with open(main_path, "r", encoding="utf-8") as f:
    tree = ast.parse(f.read())

for node in ast.walk(tree):
    if isinstance(node, ast.ImportFrom):
        names = [a.name for a in node.names]
        if node.module:
            print(f"from {node.module} import {names}")
