# Template: Documentation Coverage

name: documentation
scope: "src/**/*.py"
metric: "% documented functions"
direction: higher is better
verify: |
  python -c "
  import ast, os, sys
  total = doc = 0
  for root, _, files in os.walk('src'):
      for f in files:
          if not f.endswith('.py'): continue
          try:
              tree = ast.parse(open(os.path.join(root, f), encoding='utf-8').read())
              for node in ast.walk(tree):
                  if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                      total += 1
                      if ast.get_docstring(node): doc += 1
          except: pass
  print(f'METRIC: {round(doc/max(total,1)*100, 1)}')
  "
test: pytest tests/ -q --tb=short

## Executor

- Найди модуль с наименьшим % документированных функций
- Добавь docstrings к ОДНОМУ модулю за итерацию
- Google-style: описание, Args, Returns, Raises
- Не пиши заглушки ("TODO", "Not implemented")
- Docstring должен объяснять ЧТО и ЗАЧЕМ, а не КАК

## Reviewer

- Docstrings точно описывают поведение функций?
- Нет ли заглушек или шаблонных фраз?
- `pytest tests/ -q` — тесты проходят?
- Документированных функций стало больше?
