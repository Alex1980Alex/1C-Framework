"""One-shot: split docs/architecture/PATTERNS.md into per-pattern wiki pages."""

import re
from datetime import date
from pathlib import Path

ROOT = Path("D:/1С-Framework")
SRC = ROOT / "docs/architecture/PATTERNS.md"
OUT = ROOT / "docs/wiki/patterns"
OUT.mkdir(parents=True, exist_ok=True)

SLUGS = {
    "1.1": ("provider-pattern", "Provider Pattern", "architecture"),
    "1.2": ("strategy-pattern", "Strategy Pattern", "architecture"),
    "1.3": ("di-container", "DI Container", "architecture"),
    "1.4": ("abstract-base-class", "Abstract Base Class (ABC)", "architecture"),
    "1.5": ("registry", "Registry", "architecture"),
    "1.6": ("factory", "Factory", "architecture"),
    "1.7": ("template-method", "Template Method", "architecture"),
    "1.8": ("composite", "Composite", "architecture"),
    "1.9": ("router-classifier", "Router / Classifier", "architecture"),
    "1.10": ("pipeline", "Pipeline", "architecture"),
    "1.11": ("state-machine", "State Machine", "architecture"),
    "1.12": ("singleton", "Singleton", "architecture"),
    "1.13": ("adapter", "Adapter", "architecture"),
    "1.14": ("observer", "Observer", "architecture"),
    "1.15": ("change-detector", "Change Detector", "architecture"),
    "2.1": ("base-hook-protocol", "BaseHook Protocol", "automation"),
    "2.2": ("session-state", "SessionState", "automation"),
    "2.3": ("config-driven-routing", "Config-Driven Routing", "automation"),
    "2.4": ("fuzzy-intent-detection", "Fuzzy Intent Detection", "automation"),
    "2.5": ("multi-level-enforcement", "Multi-Level Enforcement", "automation"),
    "2.6": ("guard-gate", "Guard Gate", "automation"),
    "2.7": ("silent-observer", "Silent Observer", "automation"),
    "2.8": ("error-classifier", "Error Classifier", "automation"),
    "2.9": ("stop-gate", "Stop Gate", "automation"),
    "2.10": ("circuit-breaker", "Circuit Breaker", "automation"),
    "2.11": ("task-master", "Task Master", "automation"),
    "2.12": ("invocation-logger", "Invocation Logger", "automation"),
    "2.13": ("three-tier-pipeline", "3-Tier Pipeline", "automation"),
}

text = SRC.read_text(encoding="utf-8")
today = date.today().isoformat()

parts = re.split(r"^### (\d+\.\d+)\s+(.+?)$", text, flags=re.MULTILINE)
extracted = {}
for i in range(1, len(parts), 3):
    num = parts[i].strip()
    title = parts[i + 1].strip()
    body = parts[i + 2]
    next_top = re.search(r"^## ", body, re.MULTILINE)
    if next_top:
        body = body[: next_top.start()]
    extracted[num] = (title, body.rstrip())

print(f"Extracted {len(extracted)} patterns")

written = 0
for num, (title, body) in extracted.items():
    if num not in SLUGS:
        print(f"WARN: no slug for {num} {title}")
        continue
    slug, _, category = SLUGS[num]
    out_file = OUT / f"{slug}.md"
    fm = (
        "---\n"
        "status: active\n"
        f"tags: [pattern, {category}]\n"
        f'related: ["[[PATTERNS]]"]\n'
        f"created: {today}\n"
        "---\n\n"
    )
    heading = f"# {num} {title}\n\n"
    out_file.write_text(fm + heading + body.lstrip("\n") + "\n", encoding="utf-8")
    written += 1

print(f"Wrote {written} pattern pages to {OUT}")

arch = [(num, SLUGS[num][0], SLUGS[num][1]) for num in SLUGS if SLUGS[num][2] == "architecture"]
auto = [(num, SLUGS[num][0], SLUGS[num][1]) for num in SLUGS if SLUGS[num][2] == "automation"]

index_md = """---
status: active
tags: [architecture, patterns, automation, index]
related: ["[[overview]]", "[[triad-architecture]]", "[[ralph-wiggum]]", "[[hooks-reference]]", "[[skills-reference]]", "[[bsl-integration]]", "[[core-framework-separation]]"]
---

# Каталог паттернов фреймворка

> Index-страница: 15 архитектурных + 13 автоматизационных паттернов. Каждый паттерн вынесен в отдельную wiki-страницу в [docs/wiki/patterns/](../wiki/patterns/) для точечной ссылаемости.

---

## 1. Архитектурные паттерны (`src/pdf_framework/`)

| # | Паттерн | Wiki-страница |
|---|---------|---------------|
"""
for num, slug, title in arch:
    index_md += f"| {num} | {title} | [[{slug}]] |\n"

index_md += """
---

## 2. Паттерны автоматизации (`.claude/hooks/`)

| # | Паттерн | Wiki-страница |
|---|---------|---------------|
"""
for num, slug, title in auto:
    index_md += f"| {num} | {title} | [[{slug}]] |\n"

m3 = re.search(r"^## 3\. .*?(?=^## 4\.)", text, re.DOTALL | re.MULTILINE)
m4 = re.search(r"^## 4\. .*", text, re.DOTALL | re.MULTILINE)
if m3:
    index_md += "\n---\n\n" + m3.group(0).rstrip() + "\n"
if m4:
    index_md += "\n---\n\n" + m4.group(0).rstrip() + "\n"

SRC.write_text(index_md, encoding="utf-8")
print(f"Rewrote {SRC} as index ({len(index_md.splitlines())} lines)")
