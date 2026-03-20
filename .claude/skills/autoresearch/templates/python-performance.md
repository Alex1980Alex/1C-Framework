# Template: Python Performance

name: python-performance
scope: "src/**/*.py"
metric: avg response time (ms)
direction: lower is better
verify: |
  pytest tests/ --benchmark-json=data/bench.json -q 2>/dev/null && python -c "import json; d=json.load(open('data/bench.json')); print(round(sum(b['stats']['mean'] for b in d['benchmarks'])/len(d['benchmarks'])*1000, 2))"
test: pytest tests/ -q --tb=short

## Executor

- Профилируй один endpoint: `python -m cProfile -s cumtime`
- Найди bottleneck (I/O, CPU, memory)
- Одно изменение: кеширование, async, connection pooling, lazy loading
- Не оптимизируй то, что не является bottleneck

## Reviewer

- Benchmark ДО и ПОСЛЕ (числа, не ощущения)
- `pytest tests/ -q` — тесты проходят?
- Memory usage не вырос значительно?
- Код остался читаемым?
