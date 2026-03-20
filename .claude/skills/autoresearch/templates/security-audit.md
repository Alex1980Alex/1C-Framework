# Template: Security Audit (READ-ONLY)

name: security-audit
scope: "src/**/*.py"
metric: findings count (higher = more findings = better coverage)
direction: higher is better
verify: |
  bandit -r src/ -f json 2>/dev/null | python -c "import sys,json; d=json.load(sys.stdin); print(f\"METRIC: {len(d.get('results', []))}\")"
test: echo "Read-only mode, no tests needed"

## ВАЖНО: READ-ONLY MODE

Этот шаблон НЕ модифицирует код. Итерации = анализ разных attack vectors.

## Executor

Каждая итерация — один attack vector из STRIDE:
- **S**poofing: аутентификация, JWT, API keys
- **T**ampering: SQL injection, path traversal, command injection
- **R**epudiation: логирование, аудит
- **I**nformation Disclosure: error messages, debug info, secrets
- **D**enial of Service: rate limiting, resource exhaustion
- **E**levation of Privilege: RBAC, authorization checks

Для каждого finding:
- file:line
- OWASP Top 10 category
- STRIDE tag
- Severity (Critical/High/Medium/Low)
- Recommendation

## Reviewer

- Finding реальный (не false positive)?
- Есть file:line?
- Есть OWASP category + STRIDE tag?
- Severity обоснован?
- Recommendation конкретная (не "fix this")?
