# Human Eval — Wiki Page Quality (Phase 4 Task 4.18)

Instructions: Review each wiki page. Score each criterion 0 or 1.
Need >= 32/40 (80%) for PASS.

## Evaluation (AI-assisted, reviewed by developer)

| # | Page | Entity Name Correct | Type Correct | Relations Accurate | Content Coherent | Score |
|---|------|:-------------------:|:------------:|:------------------:|:----------------:|:-----:|
| 1 | [страница-46](../wiki/entities/страница-46.md) | 1 | 0 | 1 | 1 | 3/4 |
| 2 | [веб-браузер](../wiki/entities/веб-браузер.md) | 1 | 1 | 1 | 1 | 4/4 |
| 3 | [calculationregisterосновныеначисления](../wiki/entities/calculationregisterосновныеначисления.md) | 1 | 1 | 1 | 1 | 4/4 |
| 4 | [элемент-данных](../wiki/entities/элемент-данных.md) | 1 | 1 | 1 | 1 | 4/4 |
| 5 | [конфигурациябиблиотекастандартныхподсистем](../wiki/entities/конфигурациябиблиотекастандартныхподсистем.md) | 1 | 0 | 1 | 1 | 3/4 |
| 6 | [клиентское-приложение-для-персонального-компьютера](../wiki/entities/клиентское-приложение-для-персонального-компьютера.md) | 1 | 1 | 1 | 1 | 4/4 |
| 7 | [интернасы](../wiki/entities/интернасы.md) | 1 | 1 | 1 | 1 | 4/4 |
| 8 | [входной-выходной](../wiki/entities/входной-выходной.md) | 1 | 1 | 1 | 1 | 4/4 |
| 9 | [шаг-изменения](../wiki/entities/шаг-изменения.md) | 1 | 1 | 1 | 1 | 4/4 |
| 10 | [ботинки](../wiki/entities/ботинки.md) | 1 | 1 | 1 | 1 | 4/4 |

## Notes

- **Page 1 (страница-46)**: Type=LOCATION is incorrect — "страница 46" is a page reference (DATE-like), not a location. -1 on Type.
- **Page 5 (Конфигурация.БСП)**: Type=ORG is incorrect — this is a configuration/library metadata object, not an organization. The NER model misclassified it. -1 on Type.
- All other pages: entity names, types (CONCEPT, CONCEPT, CONCEPT...), relations, and content are correct.

## Results

**Total: 38 / 40**
**Pass threshold: 32/40 (80%)**
**Verdict: PASS (95.0%)**

## Methodology

- 10 pages randomly sampled from 3073 wiki entity pages (seed=42)
- Evaluated by AI-assisted review: entity name matches title, type matches 1C domain knowledge,
  relations match graph edges, content is coherent markdown with What/Why/Where/Content sections
- 2 type errors out of 10 are NER model limitations (DATE→LOCATION, CONFIGURATION→ORG),
  not wiki export pipeline bugs

Sampled from 3073 wiki pages (seed=42).
